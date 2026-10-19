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

int runAntiRoll(int kind, int enabled, int rate) {
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
    if (kind == 3) world.SetGravity(JPH::Vec3::sZero());
    auto& bodies = world.GetBodyInterface();
    JPH::RefConst<JPH::BoxShape> floorShape = new JPH::BoxShape(kind == 3 ? JPH::Vec3(2.5f, 0.05f, 2.5f) : kind == 4 ? JPH::Vec3(2, 0.5f, 10) : JPH::Vec3(10, 0.5f, 10));
    JPH::BodyCreationSettings floorSettings(floorShape, JPH::RVec3(kind == 4 ? 2 : 0, kind == 3 ? -0.05f : -0.5f, 0), JPH::Quat::sIdentity(), kind == 3 ? JPH::EMotionType::Dynamic : JPH::EMotionType::Static, 0);
    floorSettings.mFriction = 0;
    floorSettings.mAllowSleeping = false;
    floorSettings.mLinearDamping = floorSettings.mAngularDamping = 0;
    floorSettings.mOverrideMassProperties = JPH::EOverrideMassProperties::MassAndInertiaProvided;
    floorSettings.mMassPropertiesOverride.mMass = 200;
    floorSettings.mMassPropertiesOverride.mInertia = JPH::Mat44::sScale(JPH::Vec3::sReplicate(100));
    const auto floor = bodies.CreateAndAddBody(floorSettings, kind == 3 ? JPH::EActivation::Activate : JPH::EActivation::DontActivate);
    JPH::RefConst<JPH::BoxShape> shape = new JPH::BoxShape(JPH::Vec3(0.7f, 0.2f, 1.2f));
    JPH::BodyCreationSettings chassisSettings(shape, JPH::RVec3(0, 0.875475f, 0), JPH::Quat::sRotation(JPH::Vec3::sAxisZ(), kind >= 3 ? 0.08f : 0), JPH::EMotionType::Dynamic, 0);
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
    JPH::Ref<JPH::WheeledVehicleControllerSettings> controller = new JPH::WheeledVehicleControllerSettings;
    controller->mEngine.mMaxTorque = 0;
    JPH::VehicleDifferentialSettings front;
    front.mLeftWheel = 0;front.mRightWheel = 2;front.mEngineTorqueRatio = 0.5f;
    JPH::VehicleDifferentialSettings rear;
    rear.mLeftWheel = 1;rear.mRightWheel = 3;rear.mEngineTorqueRatio = 0.5f;
    controller->mDifferentials.push_back(front);controller->mDifferentials.push_back(rear);
    settings.mController = controller;
    for (float x : { -0.6f, 0.6f }) for (float z : { -1.0f, 1.0f }) {
        JPH::Ref<JPH::WheelSettingsWV> wheel = new JPH::WheelSettingsWV;
        wheel->mPosition = JPH::Vec3(x, 0, z);
        wheel->mRadius = 0.3f;
        wheel->mSuspensionMinLength = 0.2f;
        wheel->mSuspensionMaxLength = 0.77985f;
        wheel->mSuspensionSpring = JPH::SpringSettings(JPH::ESpringMode::StiffnessAndDamping, 1200, 160);
        wheel->mLongitudinalFriction.Clear();
        wheel->mLongitudinalFriction.AddPoint(0, 0);
        wheel->mLateralFriction.Clear();
        wheel->mLateralFriction.AddPoint(0, 0);
        settings.mWheels.push_back(wheel.GetPtr());
    }
    if (enabled != 0) for (int i : { 0, 1 }) {
        JPH::VehicleAntiRollBar bar;
        bar.mLeftWheel = i;
        bar.mRightWheel = i + 2;
        bar.mStiffness = enabled == 2 ? 0 : 1000;
        settings.mAntiRollBars.push_back(bar);
    }
    JPH::Ref<JPH::VehicleConstraint> vehicle = new JPH::VehicleConstraint(*chassisBody, settings);
    vehicle->SetVehicleCollisionTester(new JPH::VehicleCollisionTesterRay(0));
    world.AddConstraint(vehicle);
    world.AddStepListener(vehicle);
    JPH::TempAllocatorImpl allocator(1024 * 1024);
    JPH::JobSystemSingleThreaded jobs(JPH::cMaxPhysicsJobs);
    const int total = kind == 3 ? rate : kind == 4 ? rate / 4 : rate * 6;
    for (int step = 0; step <= total; ++step) {
        std::cout << "antiroll " << kind << ' ' << enabled << ' ' << rate << ' ' << step;
        writeVector(JPH::Vec3(bodies.GetPosition(chassis)));
        writeVector(bodies.GetLinearVelocity(chassis));
        const auto q = bodies.GetRotation(chassis);
        std::cout << ' ' << q.GetX() << ' ' << q.GetY() << ' ' << q.GetZ() << ' ' << q.GetW();
        writeVector(bodies.GetAngularVelocity(chassis));
        for (int i = 0; i < 4; ++i) {
            const auto* wheel = vehicle->GetWheel(i);
            std::cout << ' ' << wheel->GetSuspensionLength() << ' ' << wheel->GetSuspensionLambda() * rate << ' ' << wheel->HasContact();
            writeVector(wheel->HasContact() ? JPH::Vec3(wheel->GetContactPosition()) : JPH::Vec3::sZero());
            writeVector(wheel->HasContact() ? wheel->GetContactNormal() : JPH::Vec3::sZero());
        }
        writeVector(JPH::Vec3(bodies.GetPosition(floor)));
        writeVector(bodies.GetLinearVelocity(floor));
        const auto groundRotation = bodies.GetRotation(floor);
        std::cout << ' ' << groundRotation.GetX() << ' ' << groundRotation.GetY() << ' ' << groundRotation.GetZ() << ' ' << groundRotation.GetW();
        writeVector(bodies.GetAngularVelocity(floor));
        std::cout << '\n';
        if (step == total) break;
        if (kind == 0 && step == rate * 2) bodies.AddImpulse(chassis, JPH::Vec3(0, 500, 0));
        if ((kind == 1 || kind == 2) && step >= 2 * rate && step < 4 * rate) bodies.AddTorque(chassis, JPH::Vec3(0, 0, kind == 1 ? 40 : -40));
        if (world.Update(1.0f / rate, 1, &allocator, &jobs) != JPH::EPhysicsUpdateError::None) return 4;
    }
    world.RemoveStepListener(vehicle);
    world.RemoveConstraint(vehicle);
    vehicle = nullptr;
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
    for (int kind : { 0, 1, 2, 3, 4 }) for (int enabled : { 0, 1, 2 }) for (int rate : { 60, 120 }) {
        if (result == 0) result = Physics3D::runAntiRoll(kind, enabled, rate);
    }
    JPH::UnregisterTypes();
    JPH::Factory::sInstance = nullptr;
    return result;
}
