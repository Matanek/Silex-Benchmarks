#include <cmath>
#include <cstdlib>
#include <iostream>
#include <memory>
#include <string_view>
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
#include <Jolt/Physics/Collision/Shape/PlaneShape.h>
#include <Jolt/Physics/Vehicle/VehicleConstraint.h>
#include <Jolt/Physics/Vehicle/VehicleCollisionTester.h>
#include <Jolt/Physics/Vehicle/TrackedVehicleController.h>

namespace Physics3D {

// -----------------------------------------------------------------------------

void writeVector(JPH::Vec3Arg value) {
    std::cout << ' ' << value.GetX() << ' ' << value.GetY() << ' ' << value.GetZ();
}

// -----------------------------------------------------------------------------

int runTrackedAutomaticRamp(int scenario, int rate, bool perturb) {
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
    world.SetGravity(JPH::Vec3(0, -9.81f, 0));
    auto& bodies = world.GetBodyInterface();
    JPH::RefConst<JPH::PlaneShape> floorShape = new JPH::PlaneShape(JPH::Plane(JPH::Vec3::sAxisY(), 0));
    JPH::BodyCreationSettings floorSettings(floorShape, JPH::RVec3::sZero(), JPH::Quat::sIdentity(), JPH::EMotionType::Static, 0);
    floorSettings.mFriction = 1;
    const auto floor = bodies.CreateAndAddBody(floorSettings, JPH::EActivation::DontActivate);
    JPH::BodyID ramp;
    if (scenario == 1) {
        JPH::RefConst<JPH::BoxShape> rampShape = new JPH::BoxShape(JPH::Vec3(4.0f, 0.2f, 3.015f), 0);
        JPH::BodyCreationSettings rampSettings(rampShape, JPH::RVec3(0, 0.1f, 15.0f), JPH::Quat::sRotation(JPH::Vec3::sAxisX(), -0.1f), JPH::EMotionType::Static, 0);
        rampSettings.mFriction = 1;
        ramp = bodies.CreateAndAddBody(rampSettings, JPH::EActivation::DontActivate);
    }
    JPH::RefConst<JPH::BoxShape> shape = new JPH::BoxShape(JPH::Vec3(0.7f, 0.2f, 1.2f));
    JPH::BodyCreationSettings chassisSettings(shape, JPH::RVec3(0, 1.15f + (perturb ? 0.000001f : 0.0f), 0), JPH::Quat::sIdentity(), JPH::EMotionType::Dynamic, 0);
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
    controller->mEngine.mMaxTorque = 15;
    controller->mEngine.mMinRPM = 1000;
    controller->mEngine.mMaxRPM = 6000;
    controller->mEngine.mAngularDamping = 0;
    controller->mEngine.mInertia = 0.5f;
    controller->mEngine.mNormalizedTorque.Clear();
    controller->mEngine.mNormalizedTorque.AddPoint(0, 1);
    controller->mTransmission.mMode = JPH::ETransmissionMode::Auto;
    controller->mTransmission.mGearRatios = { 2.0f, 1.4f, 1.0f };
    controller->mTransmission.mReverseGearRatios = { -2.0f, -1.4f, -1.0f };
    controller->mTransmission.mShiftUpRPM = 1800;
    controller->mTransmission.mShiftDownRPM = 1200;
    controller->mTransmission.mSwitchTime = 0.5f;
    controller->mTransmission.mClutchReleaseTime = 0.3f;
    controller->mTransmission.mSwitchLatency = 0.5f;
    for (int index : { 0, 1 }) {
        auto& track = controller->mTracks[index];
        track.mDrivenWheel = index * 3;
        track.mWheels = { static_cast<JPH::uint>(index * 3), static_cast<JPH::uint>(index * 3 + 1), static_cast<JPH::uint>(index * 3 + 2) };
        track.mInertia = 2.0f;
        track.mAngularDamping = 0;
        track.mMaxBrakeTorque = 1500.0f;
        track.mDifferentialRatio = 6.0f;
    }
    settings.mController = controller;
    for (int index = 0; index < 6; ++index) {
        JPH::Ref<JPH::WheelSettingsTV> wheel = new JPH::WheelSettingsTV;
        wheel->mPosition = JPH::Vec3(index < 3 ? -0.6f : 0.6f, 0, static_cast<float>(index % 3 - 1));
        wheel->mRadius = 0.3f;
        wheel->mSuspensionMinLength = 0.2f;
        wheel->mSuspensionMaxLength = 0.6f;
        wheel->mSuspensionSpring = JPH::SpringSettings(JPH::ESpringMode::StiffnessAndDamping, 10000.0f, 1000.0f);
        wheel->mLongitudinalFriction = scenario == 5 ? 0.0f : 1.0f;
        wheel->mLateralFriction = scenario == 5 ? 0.0f : 0.15f;
        settings.mWheels.push_back(wheel.GetPtr());
    }
    JPH::Ref<JPH::VehicleConstraint> vehicle = new JPH::VehicleConstraint(*chassisBody, settings);
    vehicle->SetVehicleCollisionTester(new JPH::VehicleCollisionTesterRay(0));
    auto* driver = static_cast<JPH::TrackedVehicleController*>(vehicle->GetController());
    world.AddConstraint(vehicle);
    world.AddStepListener(vehicle);
    JPH::TempAllocatorImpl allocator(1024 * 1024);
    JPH::JobSystemSingleThreaded jobs(JPH::cMaxPhysicsJobs);
    for (int step = 0; step <= rate * 16; ++step) {
        std::cout << "tracked-auto-ramp " << scenario << ' ' << rate << ' ' << step;
        writeVector(JPH::Vec3(bodies.GetPosition(chassis)));
        writeVector(bodies.GetLinearVelocity(chassis));
        const auto rotation = bodies.GetRotation(chassis);
        std::cout << ' ' << rotation.GetX() << ' ' << rotation.GetY() << ' ' << rotation.GetZ() << ' ' << rotation.GetW();
        writeVector(bodies.GetAngularVelocity(chassis));
        std::cout << ' ' << driver->GetEngine().GetCurrentRPM() << ' ' << driver->GetTransmission().GetCurrentGear() << ' ' << driver->GetTransmission().GetClutchFriction();
        for (const auto& track : driver->GetTracks()) std::cout << ' ' << track.mAngularVelocity;
        for (int index = 0; index < 6; ++index) {
            const auto* wheel = vehicle->GetWheel(index);
            const bool touching = wheel->HasContact();
            std::cout << ' ' << wheel->GetSuspensionLength() << ' ' << wheel->GetSuspensionLambda() * rate << ' ' << wheel->GetAngularVelocity() << ' ' << wheel->GetRotationAngle() << ' ' << wheel->GetLongitudinalLambda() * rate << ' ' << wheel->GetLateralLambda() * rate << ' ' << touching;
            writeVector(touching ? JPH::Vec3(wheel->GetContactPosition()) : JPH::Vec3::sZero());
            writeVector(touching ? wheel->GetContactNormal() : JPH::Vec3::sZero());
            writeVector(touching ? wheel->GetContactLongitudinal() : JPH::Vec3::sZero());
        }
        std::cout << '\n';
        if (step == rate * 16) break;
        const bool driving = step >= 2 * rate && step < 6 * rate;
        const float throttle = driving ? 0.8f : 0.0f;
        const float left = 1.0f;
        const float right = 1.0f;
        driver->SetDriverInput(throttle, left, right, driving ? 0.0f : 0.04f);
        if (world.Update(1.0f / rate, 1, &allocator, &jobs) != JPH::EPhysicsUpdateError::None) return 4;
    }
    world.RemoveStepListener(vehicle);
    world.RemoveConstraint(vehicle);
    vehicle = nullptr;
    bodies.RemoveBody(chassis);
    bodies.DestroyBody(chassis);
    if (scenario == 1) { bodies.RemoveBody(ramp); bodies.DestroyBody(ramp); }
    bodies.RemoveBody(floor);
    bodies.DestroyBody(floor);
    return 0;
}

// -----------------------------------------------------------------------------

} // namespace Physics3D

int main(int argc, char** argv) {
    if (argc > 2 || (argc == 2 && std::string_view(argv[1]) != "--perturb")) return 2;
    const bool perturb = argc == 2;
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
    for (int scenario = 0; scenario < 2 && result == 0; ++scenario) for (int rate : { 60, 120 }) {
        if (result == 0) result = Physics3D::runTrackedAutomaticRamp(scenario, rate, perturb);
    }
    JPH::UnregisterTypes();
    JPH::Factory::sInstance = nullptr;
    return result;
}
