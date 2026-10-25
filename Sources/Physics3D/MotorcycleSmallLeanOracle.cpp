#include <array>
#include <cstdlib>
#include <iostream>
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
#include <Jolt/Physics/Vehicle/MotorcycleController.h>

namespace Physics3D {

// -----------------------------------------------------------------------------

float response(bool enabled, float angle, int rate) {
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
    JPH::RefConst<JPH::BoxShape> floorShape = new JPH::BoxShape(JPH::Vec3(100, 0.5f, 100));
    JPH::BodyCreationSettings floorSettings(floorShape, JPH::RVec3(0, -0.5f, 0), JPH::Quat::sIdentity(), JPH::EMotionType::Static, 0);
    floorSettings.mFriction = 0;
    const auto floor = bodies.CreateAndAddBody(floorSettings, JPH::EActivation::DontActivate);
    JPH::RefConst<JPH::BoxShape> shape = new JPH::BoxShape(JPH::Vec3(0.2f, 0.25f, 0.8f), 0);
    JPH::BodyCreationSettings chassisSettings(shape, JPH::RVec3(0, 0.875475f, 0), JPH::Quat::sRotation(JPH::Vec3::sAxisZ(), angle), JPH::EMotionType::Dynamic, 0);
    chassisSettings.mAllowSleeping = false;
    chassisSettings.mLinearDamping = 0;
    chassisSettings.mAngularDamping = 0;
    chassisSettings.mOverrideMassProperties = JPH::EOverrideMassProperties::MassAndInertiaProvided;
    chassisSettings.mMassPropertiesOverride.mMass = 100;
    chassisSettings.mMassPropertiesOverride.mInertia = JPH::Mat44::sScale(JPH::Vec3::sReplicate(100));
    auto* chassisBody = bodies.CreateBody(chassisSettings);
    if (chassisBody == nullptr) std::abort();
    const auto chassis = chassisBody->GetID();
    bodies.AddBody(chassis, JPH::EActivation::Activate);
    JPH::VehicleConstraintSettings settings;
    settings.mMaxPitchRollAngle = JPH::JPH_PI;
    JPH::Ref<JPH::MotorcycleControllerSettings> control = new JPH::MotorcycleControllerSettings;
    JPH::VehicleDifferentialSettings rearDrive;
    rearDrive.mLeftWheel = 1;
    rearDrive.mRightWheel = -1;
    rearDrive.mEngineTorqueRatio = 1;
    control->mDifferentials.push_back(rearDrive);
    control->mEngine.mMaxTorque = 0;
    control->mLeanSpringConstant = 5000;
    control->mLeanSpringDamping = 0;
    control->mLeanSpringIntegrationCoefficient = 0;
    control->mLeanSmoothingFactor = 0;
    settings.mController = control;
    for (float z : { 1.0f, -1.0f }) {
        JPH::Ref<JPH::WheelSettingsWV> wheel = new JPH::WheelSettingsWV;
        wheel->mPosition = JPH::Vec3(0, 0, z);
        wheel->mRadius = 0.3f;
        wheel->mSuspensionMinLength = 0.2f;
        wheel->mSuspensionMaxLength = 0.6f;
        wheel->mSuspensionSpring = JPH::SpringSettings(JPH::ESpringMode::StiffnessAndDamping, 10000, 1000);
        wheel->mMaxSteerAngle = 0;
        wheel->mAngularDamping = 0;
        settings.mWheels.push_back(wheel.GetPtr());
    }
    JPH::Ref<JPH::VehicleConstraint> vehicle = new JPH::VehicleConstraint(*chassisBody, settings);
    vehicle->SetVehicleCollisionTester(new JPH::VehicleCollisionTesterRay(0));
    auto* controller = static_cast<JPH::MotorcycleController*>(vehicle->GetController());
    controller->EnableLeanController(enabled);
    controller->GetTransmission().Set(1, 0);
    world.AddConstraint(vehicle);
    world.AddStepListener(vehicle);
    JPH::TempAllocatorImpl allocator(1024 * 1024);
    JPH::JobSystemSingleThreaded jobs(JPH::cMaxPhysicsJobs);
    if (world.Update(1.0f / rate, 1, &allocator, &jobs) != JPH::EPhysicsUpdateError::None) std::abort();
    if (!vehicle->GetWheel(0)->HasContact() || !vehicle->GetWheel(1)->HasContact()) std::abort();
    const float spin = bodies.GetAngularVelocity(chassis).GetZ();
    world.RemoveStepListener(vehicle);
    world.RemoveConstraint(vehicle);
    vehicle = nullptr;
    bodies.RemoveBody(chassis);
    bodies.DestroyBody(chassis);
    bodies.RemoveBody(floor);
    bodies.DestroyBody(floor);
    return spin;
}

// -----------------------------------------------------------------------------

} // namespace Physics3D

int main() {
#ifdef JPH_ENABLE_ASSERTS
    JPH::AssertFailed = [](const char* expression, const char*, const char*, JPH::uint) {
        std::cerr << "Jolt assertion: " << expression << '\n'; std::abort(); return false;
    };
#endif
    JPH::RegisterDefaultAllocator();
    JPH::Factory::sInstance = new JPH::Factory;
    JPH::RegisterTypes();
    std::cout.precision(9);
    for (int rate : { 60, 120 }) {
        for (float angle : { -0.0001f, -0.00001f, 0.00001f, 0.0001f }) {
            const float correction = (Physics3D::response(true, angle, rate) - Physics3D::response(false, angle, rate)) * rate;
            std::cout << rate << ' ' << angle << ' ' << correction << '\n';
        }
    }
    JPH::UnregisterTypes();
    delete JPH::Factory::sInstance;
    JPH::Factory::sInstance = nullptr;
}
