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
#include <Jolt/Physics/Vehicle/MotorcycleController.h>

namespace Physics3D {

void writeVector(JPH::Vec3Arg value) {
    std::cout << ' ' << value.GetX() << ' ' << value.GetY() << ' ' << value.GetZ();
}

// -----------------------------------------------------------------------------

class ObservedMotorcycle : public JPH::MotorcycleController {
    public: int kind { 0 };
    public: int rate { 60 };
    public: int step { 0 };
    public: int iterations { 0 };
    public: ObservedMotorcycle(const JPH::MotorcycleControllerSettings& settings, JPH::VehicleConstraint& vehicle) : JPH::MotorcycleController(settings, vehicle) {}
    public: JPH::Vec3 target() const { return mTargetLean; }
    public: float integral() const { return mLeanSpringIntegratedDeltaAngle; }
    public: float impulse() const { return mAppliedImpulse; }
    protected: bool SolveLongitudinalAndLateralConstraints(float dt) override {
        auto* body = mConstraint.GetVehicleBody();
        const auto oldW = body->GetAngularVelocity();
        const auto oldV = body->GetLinearVelocity();
        const auto forward = body->GetRotation() * mConstraint.GetLocalForward();
        const auto up = body->GetRotation() * mConstraint.GetLocalUp();
        const auto oldIntegral = mLeanSpringIntegratedDeltaAngle;
        const auto oldImpulse = mAppliedImpulse;
        auto weightedArm = JPH::Vec3::sZero();
        float totalLambda = 0;
        bool supported = true;
        for (const auto* wheel : mConstraint.GetWheels()) {
            supported &= wheel->HasContact() && wheel->GetSuspensionLambda() > 0;
            if (wheel->HasContact()) {
                const float lambda = wheel->GetSuspensionLambda();
                totalLambda += lambda;
                weightedArm += lambda * JPH::Vec3(wheel->GetContactPosition() - body->GetCenterOfMassPosition());
            }
        }
        const bool result = JPH::MotorcycleController::SolveLongitudinalAndLateralConstraints(dt);
        if (kind < 6) {
            std::cout << "motorcycle-solve " << kind << ' ' << rate << ' ' << step << ' ' << iterations;
            writeVector(oldW); writeVector(body->GetAngularVelocity());
            writeVector(oldV); writeVector(body->GetLinearVelocity());
            writeVector(forward); writeVector(up); writeVector(mTargetLean);
            std::cout << ' ' << oldIntegral << ' ' << mLeanSpringIntegratedDeltaAngle << ' ' << oldImpulse << ' ' << mAppliedImpulse;
            writeVector(weightedArm);
            std::cout << ' ' << totalLambda << ' ' << supported << ' ' << IsLeanControllerEnabled() << '\n';
        }
        ++iterations;
        return result;
    }
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
    if (kind == 12) world.SetGravity(JPH::Vec3(0, -3, 0));
    auto& bodies = world.GetBodyInterface();
    const bool airborne = kind >= 8 && kind <= 12;
    JPH::BodyID floor;
    if (!airborne) {
        JPH::RefConst<JPH::BoxShape> shape = new JPH::BoxShape(JPH::Vec3(100, 0.5f, 100));
        JPH::BodyCreationSettings settings(shape, JPH::RVec3(0, -0.5f, 0), JPH::Quat::sIdentity(), JPH::EMotionType::Static, 0);
        settings.mFriction = 1;
        floor = bodies.CreateAndAddBody(settings, JPH::EActivation::DontActivate);
    }
    const float roll = kind == 1 ? -0.2f : kind < 6 ? 0.2f : 0;
    JPH::RefConst<JPH::SphereShape> shape = new JPH::SphereShape(0.05f);
    JPH::BodyCreationSettings chassisSettings(shape, JPH::RVec3(0, airborne ? 100 : 0.85095f, 0), JPH::Quat::sRotation(JPH::Vec3::sAxisZ(), roll), JPH::EMotionType::Dynamic, 0);
    chassisSettings.mAllowSleeping = false;
    chassisSettings.mLinearDamping = chassisSettings.mAngularDamping = chassisSettings.mFriction = 0;
    chassisSettings.mOverrideMassProperties = JPH::EOverrideMassProperties::MassAndInertiaProvided;
    chassisSettings.mMassPropertiesOverride.mMass = 100;
    chassisSettings.mMassPropertiesOverride.mInertia = JPH::Mat44::sScale(JPH::Vec3::sReplicate(100));
    auto* chassisBody = bodies.CreateBody(chassisSettings);
    if (chassisBody == nullptr) return 3;
    const auto chassis = chassisBody->GetID();
    bodies.AddBody(chassis, JPH::EActivation::Activate);
    if (kind == 6 || kind == 7 || kind >= 13) bodies.SetLinearVelocity(chassis, JPH::Vec3(0, 0, 5));
    if (airborne) bodies.SetLinearVelocity(chassis, JPH::Vec3(0, 0, kind == 9 ? -20 : 20));
    JPH::VehicleConstraintSettings settings;
    settings.mMaxPitchRollAngle = JPH::JPH_PI;
    JPH::Ref<ObservedSettings> control = new ObservedSettings;
    control->mEngine.mMaxTorque = 0;
    JPH::VehicleDifferentialSettings rearDrive;
    rearDrive.mLeftWheel = 1;
    rearDrive.mRightWheel = -1;
    rearDrive.mEngineTorqueRatio = 1;
    control->mDifferentials.push_back(rearDrive);
    control->mLeanSpringConstant = 5000;
    control->mLeanSpringDamping = 1000;
    control->mLeanSpringIntegrationCoefficient = kind == 4 || kind == 5 ? 250 : 0;
    control->mLeanSmoothingFactor = kind == 13 ? 0 : 0.8f;
    control->mMaxLeanAngle = kind >= 14 ? 0.05f : 0.7853981633974483f;
    settings.mController = control;
    for (float z : { 1.f, -1.f }) {
        JPH::Ref<JPH::WheelSettingsWV> wheel = new JPH::WheelSettingsWV;
        wheel->mPosition = JPH::Vec3(0, 0, z);
        wheel->mRadius = 0.3f;
        wheel->mSuspensionMinLength = 0.2f;
        wheel->mSuspensionMaxLength = 0.6f;
        wheel->mSuspensionSpring = JPH::SpringSettings(JPH::ESpringMode::StiffnessAndDamping, 10000, 1000);
        wheel->mMaxSteerAngle = z > 0 ? 0.6f : 0;
        if (kind == 11) wheel->mSteeringAxis = JPH::Vec3(0, 0.866025403784f, 0.5f);
        wheel->mLongitudinalFriction.Clear(); wheel->mLongitudinalFriction.AddPoint(0, kind == 6 || kind == 7 || kind >= 13 ? 1 : 0);
        wheel->mLateralFriction.Clear(); wheel->mLateralFriction.AddPoint(0, kind == 6 || kind == 7 || kind >= 13 ? 0.15f : 0);
        settings.mWheels.push_back(wheel.GetPtr());
    }
    JPH::Ref<JPH::VehicleConstraint> vehicle = new JPH::VehicleConstraint(*chassisBody, settings);
    vehicle->SetVehicleCollisionTester(new JPH::VehicleCollisionTesterRay(0));
    auto* controller = static_cast<ObservedMotorcycle*>(vehicle->GetController());
    controller->kind = kind; controller->rate = rate;
    controller->EnableLeanController(kind != 2);
    controller->EnableLeanSteeringLimit(kind != 10 && kind != 15);
    world.AddConstraint(vehicle); world.AddStepListener(vehicle);
    JPH::TempAllocatorImpl allocator(1024 * 1024);
    JPH::JobSystemSingleThreaded jobs(JPH::cMaxPhysicsJobs);
    const int total = 4 * rate;
    for (int step = 0; step <= total; ++step) {
        std::cout << "motorcycle " << kind << ' ' << rate << ' ' << step;
        writeVector(JPH::Vec3(bodies.GetPosition(chassis))); writeVector(bodies.GetLinearVelocity(chassis));
        const auto q = bodies.GetRotation(chassis);
        std::cout << ' ' << q.GetX() << ' ' << q.GetY() << ' ' << q.GetZ() << ' ' << q.GetW();
        writeVector(bodies.GetAngularVelocity(chassis));
        writeVector(controller->target());
        std::cout << ' ' << controller->integral() << ' ' << controller->impulse() << ' ' << controller->iterations;
        for (int i = 0; i < 2; ++i) {
            const auto* wheel = static_cast<const JPH::WheelWV*>(vehicle->GetWheel(i));
            std::cout << ' ' << wheel->GetSteerAngle() << ' ' << wheel->GetSuspensionLength() << ' ' << wheel->GetSuspensionLambda() * rate << ' ' << wheel->HasContact();
            writeVector(wheel->HasContact() ? wheel->GetContactNormal() : JPH::Vec3::sZero());
            writeVector(wheel->HasContact() ? wheel->GetContactLateral() : JPH::Vec3::sZero());
            std::cout << ' ' << (wheel->HasContact() ? wheel->GetLateralLambda() : 0);
        }
        std::cout << ' ' << controller->IsLeanControllerEnabled() << ' ' << controller->IsLeanSteeringLimitEnabled() << '\n';
        if (step == total) break;
        if (kind == 3) {
            if (step == rate) controller->EnableLeanController(false);
            if (step == 2 * rate) controller->EnableLeanController(true);
        }
        if (kind == 4 && step >= rate && step < 2 * rate) bodies.AddTorque(chassis, JPH::Vec3(0, 0, 30));
        if (kind == 5 && step == rate) bodies.AddImpulse(chassis, JPH::Vec3(0, 400, 0));
        float steering = 0;
        if ((kind == 6 || kind == 7 || kind >= 13) && step >= rate && step < 3 * rate) steering = kind == 7 ? -0.35f : 0.35f;
        if (airborne) steering = kind == 9 ? -0.75f : 0.75f;
        controller->SetDriverInput(0, steering, 0, 0);
        controller->step = step + 1; controller->iterations = 0;
        if (world.Update(1.0f / rate, 1, &allocator, &jobs) != JPH::EPhysicsUpdateError::None) return 4;
    }
    world.RemoveStepListener(vehicle); world.RemoveConstraint(vehicle); vehicle = nullptr;
    bodies.RemoveBody(chassis); bodies.DestroyBody(chassis);
    if (!airborne) { bodies.RemoveBody(floor); bodies.DestroyBody(floor); }
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
    for (int kind = 0; kind < 16 && result == 0; ++kind) for (int rate : { 60, 120 }) {
        result = Physics3D::runMotorcycle(kind, rate); if (result != 0) break;
    }
    JPH::UnregisterTypes(); delete JPH::Factory::sInstance; JPH::Factory::sInstance = nullptr;
    return result;
}
