#include <array>
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
#include <Jolt/Physics/Collision/GroupFilterTable.h>
#include <Jolt/Physics/Collision/Shape/SphereShape.h>
#include <Jolt/Physics/Collision/Shape/BoxShape.h>
#include <Jolt/Physics/Vehicle/VehicleConstraint.h>
#include <Jolt/Physics/Vehicle/VehicleCollisionTester.h>
#include <Jolt/Physics/Vehicle/WheeledVehicleController.h>

namespace Physics3D {

// -----------------------------------------------------------------------------

void writeVector(JPH::Vec3Arg value) {
    std::cout << ' ' << value.GetX() << ' ' << value.GetY() << ' ' << value.GetZ();
}

// -----------------------------------------------------------------------------

int runPowertrain(int kind, int rate) {
    const bool air = kind < 3 || kind == 6 || kind == 7;
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
    auto& bodies = world.GetBodyInterface();
    JPH::RefConst<JPH::BoxShape> floorShape = new JPH::BoxShape(JPH::Vec3(50, 0.5f, 50));
    JPH::BodyCreationSettings floorSettings(floorShape, JPH::RVec3(0, -0.5f, 0), JPH::Quat::sIdentity(), JPH::EMotionType::Static, 0);
    floorSettings.mFriction = 1;
    const auto floor = bodies.CreateAndAddBody(floorSettings, JPH::EActivation::DontActivate);
    if (air) world.SetGravity(JPH::Vec3::sZero());
    JPH::RefConst<JPH::BoxShape> shape = new JPH::BoxShape(JPH::Vec3(0.7f, 0.2f, 1.2f));
    JPH::BodyCreationSettings chassisSettings(shape, JPH::RVec3(0, air ? 3.0f : 0.875475f, 0), kind == 5 ? JPH::Quat::sRotation(JPH::Vec3::sAxisY(), JPH::JPH_PI / 2) : JPH::Quat::sIdentity(), JPH::EMotionType::Dynamic, 0);
    chassisSettings.mAllowSleeping = false;
    chassisSettings.mLinearDamping = chassisSettings.mAngularDamping = chassisSettings.mFriction = 0;
    chassisSettings.mOverrideMassProperties = JPH::EOverrideMassProperties::MassAndInertiaProvided;
    chassisSettings.mMassPropertiesOverride.mMass = 100;
    chassisSettings.mMassPropertiesOverride.mInertia = JPH::Mat44::sScale(JPH::Vec3::sReplicate(100));
    chassisSettings.mLinearVelocity = kind == 10 ? JPH::Vec3(0, 0, 4.5f) : JPH::Vec3::sZero();
    auto* chassisBody = bodies.CreateBody(chassisSettings);
    if (chassisBody == nullptr) return 3;
    const auto chassis = chassisBody->GetID();
    bodies.AddBody(chassis, JPH::EActivation::Activate);
    JPH::VehicleConstraintSettings settings;
    JPH::Ref<JPH::WheeledVehicleControllerSettings> controller = new JPH::WheeledVehicleControllerSettings;
    controller->mEngine.mMaxTorque = 12;
    controller->mEngine.mMinRPM = 0;
    controller->mEngine.mMaxRPM = 6000;
    controller->mEngine.mAngularDamping = 0;
    controller->mEngine.mNormalizedTorque.Clear();
    controller->mEngine.mNormalizedTorque.AddPoint(0, 1);
    controller->mTransmission.mMode = (kind == 8 || kind == 9) ? JPH::ETransmissionMode::Auto : JPH::ETransmissionMode::Manual;
    controller->mTransmission.mGearRatios = { 1.0f, 0.5f };
    controller->mTransmission.mReverseGearRatios = { -1.0f };
    controller->mTransmission.mShiftUpRPM = 100;
    controller->mTransmission.mShiftDownRPM = 50;
    const bool asymmetric = kind == 6 || kind == 7;
    const float limit = kind == 6 ? 1.4f : FLT_MAX;
    controller->mDifferentialLimitedSlipRatio = limit;
    JPH::VehicleDifferentialSettings front;
    front.mLeftWheel = 1;front.mRightWheel = 3;
    front.mDifferentialRatio = asymmetric ? 2.0f : 3.0f;
    front.mLeftRightSplit = asymmetric ? 0.25f : 0.5f;
    front.mEngineTorqueRatio = asymmetric ? 0.3f : 0.5f;
    front.mLimitedSlipRatio = limit;
    JPH::VehicleDifferentialSettings rear;
    rear.mLeftWheel = 0;rear.mRightWheel = 2;
    rear.mDifferentialRatio = 3;
    rear.mEngineTorqueRatio = 1.0f - front.mEngineTorqueRatio;
    rear.mLimitedSlipRatio = limit;
    controller->mDifferentials.push_back(front);controller->mDifferentials.push_back(rear);
    settings.mController = controller;
    for (float x : { -0.6f, 0.6f }) for (float z : { -1.0f, 1.0f }) {
        JPH::Ref<JPH::WheelSettingsWV> wheel = new JPH::WheelSettingsWV;
        wheel->mPosition = JPH::Vec3(x, 0, z);
        wheel->mRadius = 0.3f;
        wheel->mSuspensionMinLength = 0.2f;wheel->mSuspensionMaxLength = 0.6f;
        wheel->mSuspensionSpring = JPH::SpringSettings(JPH::ESpringMode::StiffnessAndDamping, 10000, 1000);
        wheel->mAngularDamping = 0;
        wheel->mMaxSteerAngle = z > 0 ? 0.5f : 0;
        wheel->mMaxBrakeTorque = 1500;
        settings.mWheels.push_back(wheel.GetPtr());
    }
    JPH::Ref<JPH::VehicleConstraint> vehicle = new JPH::VehicleConstraint(*chassisBody, settings);
    vehicle->SetVehicleCollisionTester(new JPH::VehicleCollisionTesterRay(0));
    auto* driver = static_cast<JPH::WheeledVehicleController*>(vehicle->GetController());
    if (kind < 8 || kind == 10) driver->GetTransmission().Set(kind == 1 ? 0 : kind == 4 ? -1 : 1, kind == 2 ? 0.0f : 1.0f);
    if (asymmetric) {
        const std::array<float, 4> speeds { 3, 21, 9, 37 };
        for (int i = 0; i < 4; ++i) vehicle->GetWheel(i)->SetAngularVelocity(speeds[i]);
    }
    if (kind == 10) for (int i = 0; i < 4; ++i) vehicle->GetWheel(i)->SetAngularVelocity(15.0f);
    world.AddConstraint(vehicle);world.AddStepListener(vehicle);
    JPH::TempAllocatorImpl allocator(1024 * 1024);
    JPH::JobSystemSingleThreaded jobs(JPH::cMaxPhysicsJobs);
    const int seconds = air ? 2 : (kind == 8 || kind == 9) ? 8 : 5;
    float engineTorque = 0;
    for (int step = 0; step <= rate * seconds; ++step) {
        std::cout << "powertrain " << kind << ' ' << rate << ' ' << step;
        writeVector(JPH::Vec3(bodies.GetPosition(chassis)));
        writeVector(bodies.GetLinearVelocity(chassis));
        const auto q = bodies.GetRotation(chassis);
        std::cout << ' ' << q.GetX() << ' ' << q.GetY() << ' ' << q.GetZ() << ' ' << q.GetW();
        writeVector(bodies.GetAngularVelocity(chassis));
        for (int i = 0; i < 4; ++i) {
            const auto* wheel = static_cast<const JPH::WheelWV*>(vehicle->GetWheel(i));
            std::cout << ' ' << wheel->GetSuspensionLength() << ' ' << wheel->GetSuspensionLambda() * rate << ' ' << wheel->GetAngularVelocity() << ' ' << wheel->GetRotationAngle() << ' ' << wheel->mLongitudinalSlip << ' ' << wheel->mLateralSlip << ' ' << wheel->GetLongitudinalLambda() * rate << ' ' << wheel->GetLateralLambda() * rate << ' ' << wheel->HasContact() << ' ' << wheel->GetSteerAngle();
        }
        std::cout << ' ' << driver->GetEngine().GetCurrentRPM() << ' ' << driver->GetTransmission().GetCurrentGear() << ' ' << driver->GetTransmission().GetClutchFriction() << ' ' << driver->GetTransmission().IsSwitchingGear() << ' ' << engineTorque << '\n';
        if (step == rate * seconds) break;
        const float time = static_cast<float>(step) / rate;
        float throttle = 1, brake = 0, steering = 0;
        if (kind == 10) { throttle = 0.5f;if (time >= 0.5f && time < 2.5f) steering = 0.2f; }
        if (kind == 5) { throttle = 0.7f;if (time >= 1 && time < 3) steering = 0.2f; }
        if (((kind >= 3 && kind <= 5) || kind == 10) && time >= 3) { throttle = 0;brake = 1; }
        if (kind == 8 && time >= 4) { throttle = 0;brake = 1; }
        if (kind == 9) { if (time >= 3) throttle = -1;if (time >= 6) { throttle = 0;brake = 1; } }
        driver->SetDriverInput(throttle, steering, brake, 0);
        engineTorque = driver->GetEngine().GetTorque(std::abs(throttle) * ((kind == 8 || kind == 9) ? driver->GetTransmission().GetClutchFriction() : 1.0f));
        if (world.Update(1.0f / rate, 1, &allocator, &jobs) != JPH::EPhysicsUpdateError::None) return 4;
    }
    world.RemoveStepListener(vehicle);world.RemoveConstraint(vehicle);vehicle = nullptr;
    bodies.RemoveBody(chassis);bodies.DestroyBody(chassis);
    bodies.RemoveBody(floor);bodies.DestroyBody(floor);
    return 0;
}

// -----------------------------------------------------------------------------

} // namespace Physics3D

int main() {
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
    for (int kind : { 0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10 }) for (int rate : { 60, 120 }) {
        if (result == 0) result = Physics3D::runPowertrain(kind, rate);
    }
    JPH::UnregisterTypes();
    JPH::Factory::sInstance = nullptr;
    return result;
}
