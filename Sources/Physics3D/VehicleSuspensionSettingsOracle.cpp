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

int runSuspension(int kind, int rate) {
    const float mass = kind == 3 ? 200.0f : 100.0f;
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
    JPH::RefConst<JPH::BoxShape> floorShape = new JPH::BoxShape(JPH::Vec3(10, 0.5f, 10));
    JPH::BodyCreationSettings floorSettings(floorShape, JPH::RVec3(0, -0.5f, 0), JPH::Quat::sIdentity(), JPH::EMotionType::Static, 0);
    floorSettings.mFriction = 0;
    const auto floor = bodies.CreateAndAddBody(floorSettings, JPH::EActivation::DontActivate);
    JPH::RefConst<JPH::BoxShape> shape = new JPH::BoxShape(JPH::Vec3(0.7f, 0.2f, 1.2f));
    JPH::BodyCreationSettings chassisSettings(shape, JPH::RVec3(0, kind == 8 ? 0.7f : 1.4f, 0), (kind == 5 || kind == 6) ? JPH::Quat::sRotation(JPH::Vec3::sAxisZ(), 0.12f) : JPH::Quat::sIdentity(), JPH::EMotionType::Dynamic, 0);
    chassisSettings.mAllowSleeping = false;
    chassisSettings.mLinearDamping = chassisSettings.mAngularDamping = chassisSettings.mFriction = 0;
    chassisSettings.mOverrideMassProperties = JPH::EOverrideMassProperties::MassAndInertiaProvided;
    chassisSettings.mMassPropertiesOverride.mMass = mass;
    chassisSettings.mMassPropertiesOverride.mInertia = JPH::Mat44::sScale(JPH::Vec3::sReplicate(mass));
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
        wheel->mSuspensionMaxLength = 0.6f;
        wheel->mSuspensionSpring = JPH::SpringSettings(JPH::ESpringMode::StiffnessAndDamping, 10000, 1000);
        if (kind == 1 || kind == 7) wheel->mSuspensionPreloadLength = 0.01f;
        if (kind == 2 || kind == 3 || kind == 7) wheel->mSuspensionSpring = JPH::SpringSettings(JPH::ESpringMode::FrequencyAndDamping, 3.0f, 0.8f);
        if (kind == 4) wheel->mSuspensionSpring = JPH::SpringSettings(JPH::ESpringMode::MassNormalizedStiffnessAndDamping, 400.0f, 40.0f);
        if (kind == 5 || kind == 8) {
            wheel->mEnableSuspensionForcePoint = true;
            wheel->mSuspensionForcePoint = JPH::Vec3::sZero();
        }
        wheel->mLongitudinalFriction.Clear();
        wheel->mLongitudinalFriction.AddPoint(0, 0);
        wheel->mLateralFriction.Clear();
        wheel->mLateralFriction.AddPoint(0, 0);
        settings.mWheels.push_back(wheel.GetPtr());
    }
    JPH::Ref<JPH::VehicleConstraint> vehicle = new JPH::VehicleConstraint(*chassisBody, settings);
    vehicle->SetVehicleCollisionTester(new JPH::VehicleCollisionTesterRay(0));
    world.AddConstraint(vehicle);
    world.AddStepListener(vehicle);
    JPH::TempAllocatorImpl allocator(1024 * 1024);
    JPH::JobSystemSingleThreaded jobs(JPH::cMaxPhysicsJobs);
    const int seconds = 6;
    for (int step = 0; step <= rate * seconds; ++step) {
        std::cout << "suspension-settings " << kind << ' ' << rate << ' ' << step;
        writeVector(JPH::Vec3(bodies.GetPosition(chassis)));
        writeVector(bodies.GetLinearVelocity(chassis));
        const auto q = bodies.GetRotation(chassis);
        std::cout << ' ' << q.GetX() << ' ' << q.GetY() << ' ' << q.GetZ() << ' ' << q.GetW();
        writeVector(bodies.GetAngularVelocity(chassis));
        for (int i = 0; i < 4; ++i) {
            const auto* wheel = vehicle->GetWheel(i);
            std::cout << ' ' << wheel->GetSuspensionLength() << ' ' << wheel->GetSuspensionLambda() * rate << ' ' << wheel->HasContact();
        }
        std::cout << '\n';
        if (step == rate * seconds) break;
        if (kind == 0 && step == rate * 2) bodies.AddImpulse(chassis, JPH::Vec3(0, 500, 0));
        if (kind == 8) bodies.AddForce(chassis, JPH::Vec3(0, -20000, 0));
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
    for (int kind : { 0, 1, 2, 3, 4, 5, 6, 7, 8 }) for (int rate : { 60, 120 }) {
        if (result == 0) result = Physics3D::runSuspension(kind, rate);
    }
    JPH::UnregisterTypes();
    JPH::Factory::sInstance = nullptr;
    return result;
}
