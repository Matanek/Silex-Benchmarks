#include <cmath>
#include <cstdlib>
#include <iostream>
#include <memory>
#include <Jolt/Jolt.h>
#include <Jolt/RegisterTypes.h>
#include <Jolt/Core/Factory.h>
#include <Jolt/Core/IssueReporting.h>
#include <Jolt/Core/JobSystemSingleThreaded.h>
#include <Jolt/Core/TempAllocator.h>
#include <Jolt/Physics/PhysicsSystem.h>
#include <Jolt/Physics/Body/Body.h>
#include <Jolt/Physics/Body/BodyCreationSettings.h>
#include <Jolt/Physics/Collision/BroadPhase/BroadPhaseLayerInterfaceTable.h>
#include <Jolt/Physics/Collision/BroadPhase/ObjectVsBroadPhaseLayerFilterTable.h>
#include <Jolt/Physics/Collision/ObjectLayerPairFilterTable.h>
#include <Jolt/Physics/Collision/Shape/BoxShape.h>
#include <Jolt/Physics/Vehicle/VehicleConstraint.h>
#include <Jolt/Physics/Vehicle/VehicleCollisionTester.h>
#include <Jolt/Physics/Vehicle/TrackedVehicleController.h>

namespace Physics3D {

// -----------------------------------------------------------------------------

struct TrackInput {
    float throttle { 0.5f };
    float left { 1 };
    float right { 1 };
    float brake { 0 };
};

// -----------------------------------------------------------------------------

TrackInput inputFor(int scenario, int step, int rate) {
    TrackInput input;
    if (scenario == 1) input.left = 0.5f;
    if (scenario == 2) input.left = -1;
    if (scenario == 3) { input.left = -0.5f; input.right = -1; }
    if (scenario == 4 || scenario == 13) input.throttle = -0.5f;
    if (scenario == 7 || scenario == 8 || scenario == 15) {
        input.throttle = 0;
        input.brake = scenario == 7 ? 0.25f : 1;
    }
    if (scenario == 14 && step >= rate) input.left = -1;
    return input;
}

// -----------------------------------------------------------------------------

void writeVector(JPH::Vec3Arg value) {
    std::cout << ' ' << value.GetX() << ' ' << value.GetY() << ' ' << value.GetZ();
}

// -----------------------------------------------------------------------------

int runTrackedAir(int scenario, int rate) {
    JPH::BroadPhaseLayerInterfaceTable broadPhase(1, 1);
    broadPhase.MapObjectToBroadPhaseLayer(0, JPH::BroadPhaseLayer(0));
    JPH::ObjectLayerPairFilterTable pairFilter(1);
    pairFilter.EnableCollision(0, 0);
    JPH::ObjectVsBroadPhaseLayerFilterTable phaseFilter(broadPhase, 1, pairFilter, 1);
    JPH::PhysicsSystem world;
    world.Init(16, 0, 16, 16, broadPhase, phaseFilter, pairFilter);
    JPH::PhysicsSettings physics;
    physics.mNumVelocitySteps = 12;
    physics.mNumPositionSteps = 4;
    world.SetPhysicsSettings(physics);
    world.SetGravity(JPH::Vec3::sZero());
    auto& bodies = world.GetBodyInterface();
    JPH::RefConst<JPH::BoxShape> shape = new JPH::BoxShape(JPH::Vec3(0.7f, 0.2f, 1.2f));
    JPH::BodyCreationSettings chassisSettings(shape, JPH::RVec3(0, 3, 0), JPH::Quat::sIdentity(), JPH::EMotionType::Dynamic, 0);
    chassisSettings.mAllowSleeping = false;
    chassisSettings.mLinearDamping = chassisSettings.mAngularDamping = chassisSettings.mFriction = 0;
    chassisSettings.mOverrideMassProperties = JPH::EOverrideMassProperties::MassAndInertiaProvided;
    chassisSettings.mMassPropertiesOverride.mMass = 100;
    chassisSettings.mMassPropertiesOverride.mInertia = JPH::Mat44::sScale(JPH::Vec3::sReplicate(100));
    auto* chassisBody = bodies.CreateBody(chassisSettings);
    if (chassisBody == nullptr) return 3;
    const auto chassis = chassisBody->GetID();
    bodies.AddBody(chassis, JPH::EActivation::Activate);
    JPH::VehicleConstraintSettings settings;
    JPH::Ref<JPH::TrackedVehicleControllerSettings> controller = new JPH::TrackedVehicleControllerSettings;
    controller->mEngine.mMaxTorque = 12;
    controller->mEngine.mMinRPM = scenario == 10 ? 0 : 1000;
    controller->mEngine.mMaxRPM = 6000;
    controller->mEngine.mAngularDamping = 0.2f;
    controller->mEngine.mInertia = 0.5f;
    controller->mEngine.mNormalizedTorque.Clear();
    controller->mEngine.mNormalizedTorque.AddPoint(0, 1);
    controller->mTransmission.mMode = scenario == 12 || scenario == 13 ? JPH::ETransmissionMode::Auto : JPH::ETransmissionMode::Manual;
    controller->mTransmission.mGearRatios = { 1.0f, 0.5f };
    controller->mTransmission.mReverseGearRatios = { -1.0f, -0.5f };
    controller->mTransmission.mShiftUpRPM = 1200;
    controller->mTransmission.mShiftDownRPM = 600;
    controller->mTransmission.mSwitchTime = 0.5f;
    controller->mTransmission.mClutchReleaseTime = 0.3f;
    controller->mTransmission.mSwitchLatency = 0.5f;
    for (int index : { 0, 1 }) {
        auto& track = controller->mTracks[index];
        track.mDrivenWheel = index * 3;
        track.mWheels = { static_cast<JPH::uint>(index * 3), static_cast<JPH::uint>(index * 3 + 1), static_cast<JPH::uint>(index * 3 + 2) };
        track.mInertia = index == 0 ? 10.0f : 20.0f;
        track.mAngularDamping = 0.5f;
        track.mMaxBrakeTorque = scenario == 8 ? 5000.0f : scenario == 15 && index == 1 ? 1000.0f : 50.0f;
        track.mDifferentialRatio = index == 0 ? 3.0f : 4.0f;
    }
    settings.mController = controller;
    for (int index = 0; index < 6; ++index) {
        JPH::Ref<JPH::WheelSettingsTV> wheel = new JPH::WheelSettingsTV;
        wheel->mPosition = JPH::Vec3(index < 3 ? -0.6f : 0.6f, 0, static_cast<float>(index % 3 - 1));
        wheel->mRadius = scenario == 11 ? 0.2f + 0.1f * (index % 3) : 0.3f;
        wheel->mSuspensionMinLength = 0.2f;
        wheel->mSuspensionMaxLength = 0.6f;
        wheel->mSuspensionSpring = JPH::SpringSettings(JPH::ESpringMode::StiffnessAndDamping, 10000.0f, 1000.0f);
        wheel->mLongitudinalFriction = 4;
        wheel->mLateralFriction = 2;
        settings.mWheels.push_back(wheel.GetPtr());
    }
    JPH::Ref<JPH::VehicleConstraint> vehicle = new JPH::VehicleConstraint(*chassisBody, settings);
    vehicle->SetVehicleCollisionTester(new JPH::VehicleCollisionTesterRay(0));
    auto* driver = static_cast<JPH::TrackedVehicleController*>(vehicle->GetController());
    if (scenario != 12 && scenario != 13) driver->GetTransmission().Set(scenario == 4 ? -1 : scenario == 5 ? 0 : 1, scenario == 6 ? 0.0f : 1.0f);
    for (int index : { 0, 1 }) {
        float initial = 0;
        if (scenario == 5 || scenario == 6 || scenario == 7 || scenario == 8 || scenario == 15) initial = index == 0 ? 20.0f : 40.0f;
        if (scenario == 9) initial = 1000;
        driver->GetTracks()[index].mAngularVelocity = initial;
    }
    world.AddConstraint(vehicle);
    world.AddStepListener(vehicle);
    JPH::TempAllocatorImpl allocator(1024 * 1024);
    JPH::JobSystemSingleThreaded jobs(JPH::cMaxPhysicsJobs);
    for (int step = 0; step <= rate * 2; ++step) {
        std::cout << "tracked-air " << scenario << ' ' << rate << ' ' << step;
        writeVector(JPH::Vec3(bodies.GetPosition(chassis)));
        writeVector(bodies.GetLinearVelocity(chassis));
        const auto rotation = bodies.GetRotation(chassis);
        std::cout << ' ' << rotation.GetX() << ' ' << rotation.GetY() << ' ' << rotation.GetZ() << ' ' << rotation.GetW();
        writeVector(bodies.GetAngularVelocity(chassis));
        std::cout << ' ' << driver->GetEngine().GetCurrentRPM() << ' ' << driver->GetTransmission().GetCurrentGear() << ' ' << driver->GetTransmission().GetClutchFriction();
        for (const auto& track : driver->GetTracks()) std::cout << ' ' << track.mAngularVelocity;
        for (int index = 0; index < 6; ++index) {
            const auto* wheel = vehicle->GetWheel(index);
            std::cout << ' ' << wheel->GetAngularVelocity() << ' ' << wheel->GetRotationAngle();
        }
        std::cout << '\n';
        if (step == rate * 2) break;
        const auto input = inputFor(scenario, step, rate);
        driver->SetDriverInput(input.throttle, input.left, input.right, input.brake);
        if (world.Update(1.0f / rate, 1, &allocator, &jobs) != JPH::EPhysicsUpdateError::None) return 4;
    }
    world.RemoveStepListener(vehicle);
    world.RemoveConstraint(vehicle);
    vehicle = nullptr;
    bodies.RemoveBody(chassis);
    bodies.DestroyBody(chassis);
    return 0;
}

// -----------------------------------------------------------------------------

} // namespace Physics3D

int main(int argc, char**) {
    if (argc != 1) return 2;
#ifdef JPH_ENABLE_ASSERTS
    JPH::AssertFailed = [](const char* expression, const char*, const char*, JPH::uint) {
        std::cerr << "Jolt assertion: " << expression << '\n';
        std::abort();
        return false;
    };
#endif
    JPH::RegisterDefaultAllocator();
    auto factory = std::make_unique<JPH::Factory>();
    JPH::Factory::sInstance = factory.get();
    JPH::RegisterTypes();
    std::cout.precision(9);
    int result = 0;
    for (int scenario = 0; scenario < 16 && result == 0; ++scenario) for (int rate : { 60, 120 }) {
        if (result == 0) result = Physics3D::runTrackedAir(scenario, rate);
    }
    JPH::UnregisterTypes();
    JPH::Factory::sInstance = nullptr;
    return result;
}
