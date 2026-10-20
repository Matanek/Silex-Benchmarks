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

int runTilt(int kind, int enabled, int rate) {
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
    JPH::Quat rotation = JPH::Quat::sRotation(JPH::Vec3::sAxisZ(), 0.9f);
    JPH::Vec3 velocity = JPH::Vec3::sZero();
    JPH::Vec3 up = JPH::Vec3::sAxisY();
    if (kind == 0) velocity = JPH::Vec3(0, 0, 1);
    if (kind == 1) { rotation = JPH::Quat::sRotation(JPH::Vec3::sAxisZ(), -0.9f); velocity = JPH::Vec3(0, 0, -1); }
    if (kind == 2) { rotation = JPH::Quat::sRotation(JPH::Vec3(1, 0, 1).Normalized(), 0.8f); velocity = JPH::Vec3(0, 1, 0); }
    if (kind == 3) { rotation = JPH::Quat::sIdentity(); velocity = JPH::Vec3(0, 2, 0); }
    if (kind == 5) rotation = JPH::Quat::sRotation(JPH::Vec3::sAxisZ(), 0.2f);
    if (kind == 6) { up = JPH::Vec3::sAxisZ(); rotation = JPH::Quat::sRotation(JPH::Vec3::sAxisZ(), 0.8f) * JPH::Quat::sRotation(JPH::Vec3::sAxisX(), -JPH::JPH_PI / 2); }
    if (kind == 7) rotation = JPH::Quat::sRotation(JPH::Vec3::sAxisZ(), JPH::JPH_PI - 0.001f);
    if (kind == 8) rotation = JPH::Quat(1, 0, 0, 0);
    float height = 50;
    float limit = 0.5f;
    JPH::BodyID floor;
    if (kind == 10) {
        height = 0.875475f; rotation = JPH::Quat::sIdentity(); limit = 0.0025f;
        JPH::RefConst<JPH::BoxShape> shape = new JPH::BoxShape(JPH::Vec3(10, 0.5f, 10));
        JPH::BodyCreationSettings settings(shape, JPH::RVec3(0, -0.5f, 0), JPH::Quat::sIdentity(), JPH::EMotionType::Static, 0);
        settings.mFriction = 0;
        floor = bodies.CreateAndAddBody(settings, JPH::EActivation::DontActivate);
    }
    JPH::RefConst<JPH::SphereShape> shape = new JPH::SphereShape(0.05f);
    JPH::BodyCreationSettings chassisSettings(shape, JPH::RVec3(0, height, 0), rotation, JPH::EMotionType::Dynamic, 0);
    chassisSettings.mAllowSleeping = false;
    chassisSettings.mLinearDamping = chassisSettings.mAngularDamping = chassisSettings.mFriction = 0;
    chassisSettings.mOverrideMassProperties = JPH::EOverrideMassProperties::MassAndInertiaProvided;
    chassisSettings.mMassPropertiesOverride.mMass = 100;
    chassisSettings.mMassPropertiesOverride.mInertia = JPH::Mat44::sScale(JPH::Vec3::sReplicate(100));
    auto* chassisBody = bodies.CreateBody(chassisSettings);
    if (chassisBody == nullptr) return 3;
    const auto chassis = chassisBody->GetID();
    bodies.AddBody(chassis, JPH::EActivation::Activate);
    bodies.SetAngularVelocity(chassis, velocity);
    JPH::VehicleConstraintSettings settings;
    settings.mUp = up;
    if (kind == 6) settings.mForward = JPH::Vec3::sAxisY();
    settings.mMaxPitchRollAngle = enabled == 0 ? JPH::JPH_PI : limit;
    JPH::Ref<JPH::WheeledVehicleControllerSettings> controller = new JPH::WheeledVehicleControllerSettings;
    controller->mEngine.mMaxTorque = 0;
    JPH::VehicleDifferentialSettings front;
    front.mLeftWheel = 0; front.mRightWheel = 2; front.mEngineTorqueRatio = 0.5f;
    JPH::VehicleDifferentialSettings rear;
    rear.mLeftWheel = 1; rear.mRightWheel = 3; rear.mEngineTorqueRatio = 0.5f;
    controller->mDifferentials.push_back(front); controller->mDifferentials.push_back(rear);
    settings.mController = controller;
    for (float x : { -0.6f, 0.6f }) for (float z : { -1.0f, 1.0f }) {
        JPH::Ref<JPH::WheelSettingsWV> wheel = new JPH::WheelSettingsWV;
        wheel->mPosition = JPH::Vec3(x, 0, z);
        wheel->mRadius = 0.3f;
        wheel->mSuspensionMinLength = 0.2f;
        wheel->mSuspensionMaxLength = 0.77985f;
        wheel->mSuspensionSpring = JPH::SpringSettings(JPH::ESpringMode::StiffnessAndDamping, 1200, 160);
        wheel->mLongitudinalFriction.Clear(); wheel->mLongitudinalFriction.AddPoint(0, 0);
        wheel->mLateralFriction.Clear(); wheel->mLateralFriction.AddPoint(0, 0);
        settings.mWheels.push_back(wheel.GetPtr());
    }
    if (kind == 10) for (int i : { 0, 1 }) {
        JPH::VehicleAntiRollBar bar;
        bar.mLeftWheel = i; bar.mRightWheel = i + 2; bar.mStiffness = 1000;
        settings.mAntiRollBars.push_back(bar);
    }
    JPH::Ref<JPH::VehicleConstraint> vehicle = new JPH::VehicleConstraint(*chassisBody, settings);
    vehicle->SetVehicleCollisionTester(new JPH::VehicleCollisionTesterRay(0));
    world.AddConstraint(vehicle); world.AddStepListener(vehicle);
    JPH::TempAllocatorImpl allocator(1024 * 1024);
    JPH::JobSystemSingleThreaded jobs(JPH::cMaxPhysicsJobs);
    const int total = (kind == 10 ? 4 : 2) * rate;
    for (int step = 0; step <= total; ++step) {
        std::cout << "tilt " << kind << ' ' << enabled << ' ' << rate << ' ' << step;
        writeVector(JPH::Vec3(bodies.GetPosition(chassis))); writeVector(bodies.GetLinearVelocity(chassis));
        const auto q = bodies.GetRotation(chassis);
        std::cout << ' ' << q.GetX() << ' ' << q.GetY() << ' ' << q.GetZ() << ' ' << q.GetW();
        writeVector(bodies.GetAngularVelocity(chassis));
        for (int i = 0; i < 4; ++i) {
            const auto* wheel = vehicle->GetWheel(i);
            std::cout << ' ' << wheel->GetSuspensionLength() << ' ' << wheel->GetSuspensionLambda() * rate << ' ' << wheel->HasContact();
        }
        writeVector(vehicle->GetWorldUp()); std::cout << ' ' << vehicle->GetMaxPitchRollAngle() << '\n';
        if (step == total) break;
        if (kind == 4 && enabled == 1) {
            if (step == rate / 2) vehicle->SetMaxPitchRollAngle(JPH::JPH_PI);
            if (step == rate * 3 / 2) vehicle->SetMaxPitchRollAngle(0.35f);
        }
        if (kind == 5) {
            if (step == rate / 2) world.SetGravity(JPH::Vec3(-9.81f, 0, 0));
            if (step == rate) world.SetGravity(JPH::Vec3::sZero());
        }
        if (kind == 9 && step == rate / 2) bodies.SetRotation(chassis, JPH::Quat(1, 0, 0, 0), JPH::EActivation::Activate);
        JPH::Vec3 torque = JPH::Vec3::sZero();
        if (step >= rate / 2 && step < rate * 3 / 2) {
            if (kind == 0) torque = JPH::Vec3(0, 0, 50);
            if (kind == 1) torque = JPH::Vec3(0, 0, -50);
            if (kind == 2) torque = JPH::Vec3(1, 0, 1).Normalized() * 50;
            if (kind == 3) torque = JPH::Vec3(0, 2, 0);
            if (kind == 4) torque = JPH::Vec3(0, 0, 100);
        }
        if (kind == 10 && step >= rate / 4 && step < rate * 3 / 4) torque = JPH::Vec3(0, 0, 40);
        if (kind == 10 && step == rate) bodies.AddImpulse(chassis, JPH::Vec3(0, 500, 0));
        bodies.AddTorque(chassis, torque);
        if (world.Update(1.0f / rate, 1, &allocator, &jobs) != JPH::EPhysicsUpdateError::None) return 4;
    }
    world.RemoveStepListener(vehicle); world.RemoveConstraint(vehicle); vehicle = nullptr;
    bodies.RemoveBody(chassis); bodies.DestroyBody(chassis);
    if (kind == 10) { bodies.RemoveBody(floor); bodies.DestroyBody(floor); }
    return 0;
}

// -----------------------------------------------------------------------------

} // namespace Physics3D

int main() {
#ifdef JPH_ENABLE_ASSERTS
    JPH::AssertFailed = [](const char* expression, const char*, const char*, JPH::uint) {
        std::cerr << "Jolt assertion: " << expression << '\n'; std::abort(); return false;
    };
#endif
    JPH::RegisterDefaultAllocator(); JPH::Factory::sInstance = new JPH::Factory; JPH::RegisterTypes();
    std::cout.precision(9);
    int result = 0;
    for (int kind = 0; kind < 11 && result == 0; ++kind) for (int enabled : { 0, 1 }) for (int rate : { 60, 120 }) {
        result = Physics3D::runTilt(kind, enabled, rate); if (result != 0) break;
    }
    JPH::UnregisterTypes(); delete JPH::Factory::sInstance; JPH::Factory::sInstance = nullptr;
    return result;
}
