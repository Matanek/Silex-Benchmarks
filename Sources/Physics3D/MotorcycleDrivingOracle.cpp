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

void writeVector(JPH::Vec3Arg value) {
    std::cout << ' ' << value.GetX() << ' ' << value.GetY() << ' ' << value.GetZ();
}

// -----------------------------------------------------------------------------

class ObservedMotorcycle : public JPH::MotorcycleController {
    public: ObservedMotorcycle(const JPH::MotorcycleControllerSettings& settings, JPH::VehicleConstraint& vehicle) : JPH::MotorcycleController(settings, vehicle) {}
    public: JPH::Vec3 target() const { return mTargetLean; }
};

// -----------------------------------------------------------------------------

class ObservedSettings : public JPH::MotorcycleControllerSettings {
    public: JPH::VehicleController* ConstructController(JPH::VehicleConstraint& vehicle) const override {
        return new ObservedMotorcycle(*this, vehicle);
    }
};

// -----------------------------------------------------------------------------

int runMotorcycle(int kind, int rate) {
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
    floorSettings.mFriction = 1;
    const auto floor = bodies.CreateAndAddBody(floorSettings, JPH::EActivation::DontActivate);
    JPH::RefConst<JPH::BoxShape> shape = new JPH::BoxShape(JPH::Vec3(0.2f, 0.25f, 0.8f), 0);
    JPH::BodyCreationSettings chassisSettings(shape, JPH::RVec3(0, 1.05f, 0), JPH::Quat::sIdentity(), JPH::EMotionType::Dynamic, 0);
    chassisSettings.mAllowSleeping = false;
    chassisSettings.mLinearDamping = chassisSettings.mAngularDamping = 0;
    chassisSettings.mFriction = 0.2f;
    chassisSettings.mOverrideMassProperties = JPH::EOverrideMassProperties::MassAndInertiaProvided;
    chassisSettings.mMassPropertiesOverride.mMass = 100;
    chassisSettings.mMassPropertiesOverride.mInertia = JPH::Mat44::sScale(JPH::Vec3::sReplicate(100));
    auto* chassisBody = bodies.CreateBody(chassisSettings);
    if (chassisBody == nullptr) return 3;
    const auto chassis = chassisBody->GetID();
    bodies.AddBody(chassis, JPH::EActivation::Activate);
    JPH::VehicleConstraintSettings settings;
    settings.mMaxPitchRollAngle = JPH::JPH_PI;
    JPH::Ref<ObservedSettings> control = new ObservedSettings;
    control->mEngine.mMaxTorque = 20;
    control->mEngine.mInertia = 0.05f;
    control->mEngine.mAngularDamping = 0;
    control->mEngine.mMinRPM = 0;
    control->mEngine.mMaxRPM = 6000;
    control->mEngine.mNormalizedTorque.Clear(); control->mEngine.mNormalizedTorque.AddPoint(0, 1);
    control->mTransmission.mMode = JPH::ETransmissionMode::Manual;
    control->mTransmission.mGearRatios = { 3 };
    JPH::VehicleDifferentialSettings rearDrive;
    rearDrive.mLeftWheel = 1;
    rearDrive.mRightWheel = -1;
    rearDrive.mEngineTorqueRatio = 1;
    control->mDifferentials.push_back(rearDrive);
    control->mLeanSpringConstant = 5000;
    control->mLeanSpringDamping = 1000;
    control->mLeanSpringIntegrationCoefficient = 0;
    control->mLeanSmoothingFactor = 0.8f;
    control->mMaxLeanAngle = JPH::JPH_PI / 4;
    settings.mController = control;
    for (float z : { 1.f, -1.f }) {
        JPH::Ref<JPH::WheelSettingsWV> wheel = new JPH::WheelSettingsWV;
        wheel->mPosition = JPH::Vec3(0, 0, z);
        wheel->mRadius = 0.3f;
        wheel->mSuspensionMinLength = 0.2f;
        wheel->mSuspensionMaxLength = 0.6f;
        wheel->mSuspensionSpring = JPH::SpringSettings(JPH::ESpringMode::StiffnessAndDamping, 10000, 1000);
        wheel->mMaxSteerAngle = z > 0 ? 0.6f : 0;
        wheel->mMaxBrakeTorque = 300; wheel->mMaxHandBrakeTorque = 0;
        wheel->mLongitudinalFriction.Clear(); wheel->mLongitudinalFriction.AddPoint(0, kind == 3 ? 0 : 1);
        wheel->mLateralFriction.Clear(); wheel->mLateralFriction.AddPoint(0, kind == 3 ? 0 : 1);
        settings.mWheels.push_back(wheel.GetPtr());
    }
    JPH::Ref<JPH::VehicleConstraint> vehicle = new JPH::VehicleConstraint(*chassisBody, settings);
    vehicle->SetVehicleCollisionTester(new JPH::VehicleCollisionTesterRay(0));
    auto* controller = static_cast<ObservedMotorcycle*>(vehicle->GetController());
    controller->EnableLeanController(kind != 5);
    controller->GetTransmission().Set(1, 0);
    world.AddConstraint(vehicle); world.AddStepListener(vehicle);
    JPH::TempAllocatorImpl allocator(1024 * 1024);
    JPH::JobSystemSingleThreaded jobs(JPH::cMaxPhysicsJobs);
    const int total = 8 * rate;
    for (int step = 0; step <= total; ++step) {
        std::cout << "motorcycle-driving " << kind << ' ' << rate << ' ' << step;
        writeVector(JPH::Vec3(bodies.GetPosition(chassis))); writeVector(bodies.GetLinearVelocity(chassis));
        const auto q = bodies.GetRotation(chassis);
        std::cout << ' ' << q.GetX() << ' ' << q.GetY() << ' ' << q.GetZ() << ' ' << q.GetW();
        writeVector(bodies.GetAngularVelocity(chassis));
        writeVector(controller->target());
        std::cout << ' ' << controller->GetEngine().GetCurrentRPM() << ' ' << controller->GetTransmission().GetCurrentGear() << ' ' << controller->GetTransmission().GetClutchFriction();
        for (int i = 0; i < 2; ++i) {
            const auto* wheel = static_cast<const JPH::WheelWV*>(vehicle->GetWheel(i));
            std::cout << ' ' << wheel->GetSteerAngle() << ' ' << wheel->GetSuspensionLength() << ' ' << wheel->GetSuspensionLambda() * rate << ' ' << wheel->HasContact()
                << ' ' << wheel->GetAngularVelocity() << ' ' << wheel->GetRotationAngle()
                << ' ' << (wheel->HasContact() ? wheel->GetLongitudinalLambda() * rate : 0) << ' ' << (wheel->HasContact() ? wheel->GetLateralLambda() * rate : 0);
            writeVector(wheel->HasContact() ? JPH::Vec3(wheel->GetContactPosition()) : JPH::Vec3::sZero());
            writeVector(wheel->HasContact() ? wheel->GetContactNormal() : JPH::Vec3::sZero());
            writeVector(wheel->HasContact() ? wheel->GetContactLongitudinal() : JPH::Vec3::sZero());
        }
        std::cout << ' ' << controller->IsLeanControllerEnabled() << ' ' << controller->IsLeanSteeringLimitEnabled() << '\n';
        if (step == total) break;
        const bool driving = kind < 4 && step >= 2 * rate && step < 4 * rate;
        if (kind >= 4 && step == 2 * rate) bodies.AddAngularImpulse(chassis, JPH::Vec3(0, 0, 150));
        float steering = 0;
        if (driving && (kind == 1 || kind == 2)) steering = kind == 1 ? 0.35f : -0.35f;
        controller->GetTransmission().Set(1, driving ? 1 : 0);
        controller->SetDriverInput(driving ? 0.8f : 0, steering, driving ? 0 : 0.35f, 0);
        if (world.Update(1.0f / rate, 1, &allocator, &jobs) != JPH::EPhysicsUpdateError::None) return 4;
    }
    world.RemoveStepListener(vehicle); world.RemoveConstraint(vehicle); vehicle = nullptr;
    bodies.RemoveBody(chassis); bodies.DestroyBody(chassis);
    bodies.RemoveBody(floor); bodies.DestroyBody(floor);
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
    for (int kind = 0; kind < 6 && result == 0; ++kind) for (int rate : { 60, 120 }) {
        result = Physics3D::runMotorcycle(kind, rate); if (result != 0) break;
    }
    JPH::UnregisterTypes(); delete JPH::Factory::sInstance; JPH::Factory::sInstance = nullptr;
    return result;
}
