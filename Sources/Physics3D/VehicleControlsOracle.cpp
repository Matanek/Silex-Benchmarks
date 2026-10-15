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

int runControls(int kind, int rate) {
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
    if (kind == 7) world.SetGravity(JPH::Vec3::sZero());
    JPH::RefConst<JPH::BoxShape> shape = new JPH::BoxShape(JPH::Vec3(0.7f, 0.2f, 1.2f));
    JPH::BodyCreationSettings chassisSettings(shape, JPH::RVec3(0, kind == 7 ? 3.0f : 0.875475f, 0), kind == 6 ? JPH::Quat::sRotation(JPH::Vec3::sAxisY(), JPH::JPH_PI / 2) : JPH::Quat::sIdentity(), JPH::EMotionType::Dynamic, 0);
    chassisSettings.mAllowSleeping = false;
    chassisSettings.mLinearDamping = chassisSettings.mAngularDamping = chassisSettings.mFriction = 0;
    chassisSettings.mOverrideMassProperties = JPH::EOverrideMassProperties::MassAndInertiaProvided;
    chassisSettings.mMassPropertiesOverride.mMass = 100;
    chassisSettings.mMassPropertiesOverride.mInertia = JPH::Mat44::sScale(JPH::Vec3::sReplicate(100));
    chassisSettings.mLinearVelocity = kind == 6 ? JPH::Vec3(3, 0, 0) : kind == 2 ? JPH::Vec3(0, 0, -3) : kind == 7 ? JPH::Vec3::sZero() : JPH::Vec3(0, 0, 3);
    auto* chassisBody = bodies.CreateBody(chassisSettings);
    if (chassisBody == nullptr) return 3;
    const auto chassis = chassisBody->GetID();
    bodies.AddBody(chassis, JPH::EActivation::Activate);
    JPH::VehicleConstraintSettings settings;
    JPH::Ref<JPH::WheeledVehicleControllerSettings> controller = new JPH::WheeledVehicleControllerSettings;
    controller->mEngine.mMaxTorque = 0;
    controller->mTransmission.mMode = JPH::ETransmissionMode::Manual;
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
        wheel->mAngularDamping = 0;
        wheel->mMaxSteerAngle = z > 0 ? 0.5f : 0;
        wheel->mMaxBrakeTorque = kind == 0 ? 1.5f : kind == 3 ? 0 : kind == 7 ? 0.9f : 1500;
        wheel->mMaxHandBrakeTorque = kind == 3 && z < 0 ? 20.0f : 0;
        settings.mWheels.push_back(wheel.GetPtr());
    }
    JPH::Ref<JPH::VehicleConstraint> vehicle = new JPH::VehicleConstraint(*chassisBody, settings);
    vehicle->SetVehicleCollisionTester(new JPH::VehicleCollisionTesterRay(0));
    static_cast<JPH::WheeledVehicleController*>(vehicle->GetController())->GetTransmission().Set(0, 0);
    for (int i = 0; i < 4; ++i) vehicle->GetWheel(i)->SetAngularVelocity(kind == 7 ? 10.0f * (i + 1) : kind == 2 ? -10.0f : 10.0f);
    world.AddConstraint(vehicle);
    world.AddStepListener(vehicle);
    JPH::TempAllocatorImpl allocator(1024 * 1024);
    JPH::JobSystemSingleThreaded jobs(JPH::cMaxPhysicsJobs);
    const int seconds = kind == 7 ? 2 : 4;
    std::array<float, 4> previousOmega {};
    for (int step = 0; step <= rate * seconds; ++step) {
        std::cout << "controls " << kind << ' ' << rate << ' ' << step;
        writeVector(JPH::Vec3(bodies.GetPosition(chassis)));
        writeVector(bodies.GetLinearVelocity(chassis));
        const auto q = bodies.GetRotation(chassis);
        std::cout << ' ' << q.GetX() << ' ' << q.GetY() << ' ' << q.GetZ() << ' ' << q.GetW();
        writeVector(bodies.GetAngularVelocity(chassis));
        for (int i = 0; i < 4; ++i) {
            const auto* wheel = static_cast<const JPH::WheelWV*>(vehicle->GetWheel(i));
            std::cout << ' ' << wheel->GetSuspensionLength() << ' ' << wheel->GetSuspensionLambda() * rate << ' ' << wheel->GetAngularVelocity() << ' ' << wheel->GetRotationAngle() << ' ' << wheel->mLongitudinalSlip << ' ' << wheel->mLateralSlip << ' ' << wheel->GetLongitudinalLambda() * rate << ' ' << wheel->GetLateralLambda() * rate << ' ' << wheel->HasContact() << ' ' << wheel->GetSteerAngle() << ' ' << (step == 0 ? 0 : (0.9f * (wheel->GetAngularVelocity() - previousOmega[i]) + 0.3f * wheel->GetLongitudinalLambda()) * rate);
        }
        std::cout << '\n';
        if (step == rate * seconds) break;
        const float time = static_cast<float>(step) / rate;
        float steering = 0, brake = 0, handbrake = 0;
        if (time >= 0.5f && time < 2.5f) steering = kind == 4 || kind == 6 ? 0.2f : kind == 5 ? -0.2f : 0;
        if (time >= 1 && time < 3) {
            if (kind <= 2) brake = 1;
            if (kind == 3) handbrake = 1;
        }
        if (kind == 6 && time >= 2 && time < 3) brake = 0.3f;
        if (kind == 7) brake = 1;
        static_cast<JPH::WheeledVehicleController*>(vehicle->GetController())->SetDriverInput(0, steering, brake, handbrake);
        for (int i = 0; i < 4; ++i) previousOmega[i] = vehicle->GetWheel(i)->GetAngularVelocity();
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
    for (int kind : { 0, 1, 2, 3, 4, 5, 6, 7 }) for (int rate : { 60, 120 }) {
        if (result == 0) result = Physics3D::runControls(kind, rate);
    }
    JPH::UnregisterTypes();
    JPH::Factory::sInstance = nullptr;
    return result;
}
