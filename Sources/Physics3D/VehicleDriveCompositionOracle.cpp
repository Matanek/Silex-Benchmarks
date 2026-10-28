#include <cmath>
#include <cstdlib>
#include <iostream>
#include <limits>
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
#include <Jolt/Physics/Vehicle/WheeledVehicleController.h>
#include <Jolt/Physics/Vehicle/TrackedVehicleController.h>
#include <Jolt/Physics/Vehicle/MotorcycleController.h>

namespace Physics3D {

// -----------------------------------------------------------------------------

int drivePhase(int step, int rate) {
    if (step < 3 * rate / 2) return 0;
    if (step < 7 * rate / 2) return 1;
    if (step < 9 * rate / 2) return 2;
    if (step < 11 * rate / 2) return 3;
    if (step < 8 * rate) return 4;
    if (step < 10 * rate) return 5;
    return 6;
}

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

void configureEngine(JPH::VehicleEngineSettings& engine, int family) {
    engine.mMaxTorque = family == 1 ? 15 : 20;
    engine.mMinRPM = family == 1 ? 1000 : 0;
    engine.mMaxRPM = 6000; engine.mInertia = 0.5f; engine.mAngularDamping = 0;
    engine.mNormalizedTorque.Clear(); engine.mNormalizedTorque.AddPoint(0, 1);
}

// -----------------------------------------------------------------------------

int runDrive(int family, int detector, int sign, int rate) {
    JPH::BroadPhaseLayerInterfaceTable broadPhase(1, 1);
    broadPhase.MapObjectToBroadPhaseLayer(0, JPH::BroadPhaseLayer(0));
    JPH::ObjectLayerPairFilterTable pairFilter(1); pairFilter.EnableCollision(0, 0);
    JPH::ObjectVsBroadPhaseLayerFilterTable phaseFilter(broadPhase, 1, pairFilter, 1);
    JPH::PhysicsSystem world;
    world.Init(16, 0, 16, 16, broadPhase, phaseFilter, pairFilter);
    JPH::PhysicsSettings physics; physics.mNumVelocitySteps = 12; physics.mNumPositionSteps = 4;
    world.SetPhysicsSettings(physics);
    auto& bodies = world.GetBodyInterface();
    JPH::BodyCreationSettings groundSettings(new JPH::BoxShape(JPH::Vec3(100, 0.5f, 100), 0),
        JPH::RVec3(0, -0.5f, 0), JPH::Quat::sIdentity(), JPH::EMotionType::Static, 0);
    groundSettings.mFriction = 1; groundSettings.mRestitution = 0;
    const auto ground = bodies.CreateAndAddBody(groundSettings, JPH::EActivation::DontActivate);
    const auto half = family == 2 ? JPH::Vec3(0.2f, 0.25f, 0.8f) : JPH::Vec3(0.7f, 0.2f, 1.2f);
    JPH::BodyCreationSettings bodySettings(new JPH::BoxShape(half, 0), JPH::RVec3(0, family == 2 ? 1.05f : 1.15f, 0),
        JPH::Quat::sIdentity(), JPH::EMotionType::Dynamic, 0);
    bodySettings.mFriction = bodySettings.mLinearDamping = bodySettings.mAngularDamping = 0;
    bodySettings.mAllowSleeping = false;
    bodySettings.mOverrideMassProperties = JPH::EOverrideMassProperties::MassAndInertiaProvided;
    bodySettings.mMassPropertiesOverride.mMass = 100;
    bodySettings.mMassPropertiesOverride.mInertia = JPH::Mat44::sScale(JPH::Vec3::sReplicate(100));
    auto* body = bodies.CreateBody(bodySettings); if (body == nullptr) return 3;
    const auto chassis = body->GetID(); bodies.AddBody(chassis, JPH::EActivation::Activate);
    JPH::VehicleConstraintSettings settings;
    if (family == 1) {
        JPH::Ref<JPH::TrackedVehicleControllerSettings> control = new JPH::TrackedVehicleControllerSettings;
        configureEngine(control->mEngine, family);
        control->mTransmission.mMode = JPH::ETransmissionMode::Manual;
        control->mTransmission.mGearRatios = { 1 }; control->mTransmission.mReverseGearRatios = { -1 };
        for (int i : { 0, 1 }) {
            auto& track = control->mTracks[i]; track.mDrivenWheel = 2 * i;
            track.mWheels = { static_cast<JPH::uint>(2 * i), static_cast<JPH::uint>(2 * i + 1) };
            track.mInertia = 2; track.mAngularDamping = 0; track.mMaxBrakeTorque = 1500; track.mDifferentialRatio = 6;
        }
        settings.mController = control;
    } else {
        JPH::Ref<JPH::WheeledVehicleControllerSettings> control;
        if (family == 2) {
            JPH::Ref<ObservedSettings> motorcycle = new ObservedSettings;
            motorcycle->mLeanSpringConstant = 5000; motorcycle->mLeanSpringDamping = 1000;
            motorcycle->mLeanSpringIntegrationCoefficient = 0; motorcycle->mLeanSmoothingFactor = 0.8f;
            motorcycle->mMaxLeanAngle = JPH::JPH_PI / 4;
            control = motorcycle.GetPtr();
        } else control = new JPH::WheeledVehicleControllerSettings;
        configureEngine(control->mEngine, family);
        control->mTransmission.mMode = JPH::ETransmissionMode::Manual;
        control->mTransmission.mGearRatios = { family == 2 ? 3.0f : 1.0f };
        control->mTransmission.mReverseGearRatios = { family == 2 ? -3.0f : -1.0f };
        JPH::VehicleDifferentialSettings drive;
        drive.mLeftWheel = family == 2 ? 1 : 0; drive.mRightWheel = family == 2 ? -1 : 2;
        drive.mDifferentialRatio = family == 2 ? 1 : 3;
        drive.mLimitedSlipRatio = std::numeric_limits<float>::max();
        control->mDifferentialLimitedSlipRatio = std::numeric_limits<float>::max();
        control->mDifferentials.push_back(drive); settings.mController = control;
    }
    const int count = family == 2 ? 2 : 4;
    for (int i = 0; i < count; ++i) {
        const float x = family == 2 ? 0 : (i < 2 ? -0.6f : 0.6f);
        const float z = family == 2 ? (i == 0 ? 1.0f : -1.0f) : (i % 2 == 0 ? -1.0f : 1.0f);
        JPH::Ref<JPH::WheelSettings> wheel;
        if (family == 1) {
            JPH::Ref<JPH::WheelSettingsTV> tracked = new JPH::WheelSettingsTV;
            tracked->mLongitudinalFriction = 1; tracked->mLateralFriction = 0.15f; wheel = tracked.GetPtr();
        } else {
            JPH::Ref<JPH::WheelSettingsWV> wheeled = new JPH::WheelSettingsWV;
            wheeled->mMaxSteerAngle = z > 0 ? (family == 2 ? 0.6f : 0.5f) : 0;
            wheeled->mMaxBrakeTorque = 300; wheeled->mMaxHandBrakeTorque = 0; wheeled->mAngularDamping = 0;
            wheel = wheeled.GetPtr();
        }
        wheel->mPosition = JPH::Vec3(x, 0, z); wheel->mRadius = 0.3f; wheel->mWidth = 0.4f;
        wheel->mSuspensionMinLength = 0.2f; wheel->mSuspensionMaxLength = 0.6f;
        wheel->mSuspensionSpring = JPH::SpringSettings(JPH::ESpringMode::StiffnessAndDamping, 10000, 1000);
        settings.mWheels.push_back(wheel.GetPtr());
    }
    JPH::Ref<JPH::VehicleConstraint> vehicle = new JPH::VehicleConstraint(*body, settings);
    const float slope = family == 2 ? JPH::JPH_PI / 2 - 0.000001f : JPH::JPH_PI / 3;
    if (detector == 0) vehicle->SetVehicleCollisionTester(new JPH::VehicleCollisionTesterRay(0, JPH::Vec3::sAxisY(), slope));
    else if (detector == 1) vehicle->SetVehicleCollisionTester(new JPH::VehicleCollisionTesterCastSphere(0, 0.3f, JPH::Vec3::sAxisY(), slope));
    else vehicle->SetVehicleCollisionTester(new JPH::VehicleCollisionTesterCastCylinder(0, 0));
    auto* tracked = family == 1 ? static_cast<JPH::TrackedVehicleController*>(vehicle->GetController()) : nullptr;
    auto* wheeled = family == 1 ? nullptr : static_cast<JPH::WheeledVehicleController*>(vehicle->GetController());
    auto& engine = family == 1 ? tracked->GetEngine() : wheeled->GetEngine();
    auto& transmission = family == 1 ? tracked->GetTransmission() : wheeled->GetTransmission();
    engine.SetCurrentRPM(family == 1 ? 1000 : 0); transmission.Set(1, 0);
    world.AddConstraint(vehicle); world.AddStepListener(vehicle);
    JPH::TempAllocatorImpl allocator(1024 * 1024); JPH::JobSystemSingleThreaded jobs(JPH::cMaxPhysicsJobs);
    float engineTorque = 0;
    for (int step = 0; step <= 12 * rate; ++step) {
        const int previous = step == 0 ? 0 : step - 1;
        std::cout << "drive-body " << family << ' ' << detector << ' ' << sign << ' ' << rate << ' ' << step;
        writeVector(JPH::Vec3(bodies.GetPosition(chassis))); writeVector(bodies.GetLinearVelocity(chassis));
        const auto q = bodies.GetRotation(chassis);
        std::cout << ' ' << q.GetX() << ' ' << q.GetY() << ' ' << q.GetZ() << ' ' << q.GetW();
        writeVector(bodies.GetAngularVelocity(chassis));
        std::cout << ' ' << engine.GetCurrentRPM() << ' ' << transmission.GetCurrentGear() << ' ' << transmission.GetClutchFriction()
            << ' ' << engineTorque << ' ' << bodies.GetFriction(ground) << ' ' << drivePhase(previous, rate);
        writeVector(family == 2 ? static_cast<ObservedMotorcycle*>(vehicle->GetController())->target() : JPH::Vec3::sZero());
        std::cout << ' ' << (tracked == nullptr ? 0 : tracked->GetTracks()[0].mAngularVelocity)
            << ' ' << (tracked == nullptr ? 0 : tracked->GetTracks()[1].mAngularVelocity) << '\n';
        for (int i = 0; i < count; ++i) {
            const auto* wheel = vehicle->GetWheel(i); const bool touching = wheel->HasContact();
            const auto* tire = family == 1 ? nullptr : static_cast<const JPH::WheelWV*>(wheel);
            std::cout << "drive-wheel " << family << ' ' << detector << ' ' << sign << ' ' << rate << ' ' << step << ' ' << i;
            std::cout << ' ' << wheel->GetSuspensionLength() << ' ' << wheel->GetSuspensionLambda() * rate
                << ' ' << wheel->GetAngularVelocity() << ' ' << wheel->GetRotationAngle()
                << ' ' << (tire == nullptr ? 0 : tire->mLongitudinalSlip) << ' ' << (tire == nullptr ? 0 : tire->mLateralSlip)
                << ' ' << wheel->GetLongitudinalLambda() * rate << ' ' << wheel->GetLateralLambda() * rate
                << ' ' << touching << ' ' << (tire == nullptr ? 0 : tire->GetSteerAngle());
            writeVector(touching ? JPH::Vec3(wheel->GetContactPosition()) : JPH::Vec3::sZero());
            writeVector(touching ? wheel->GetContactNormal() : JPH::Vec3::sZero());
            writeVector(touching ? wheel->GetContactLongitudinal() : JPH::Vec3::sZero()); std::cout << '\n';
        }
        if (step == 12 * rate) break;
        if (step == 9 * rate / 2) bodies.SetFriction(ground, 0);
        if (step == 5 * rate) bodies.SetFriction(ground, 1);
        const int phase = drivePhase(step, rate);
        float throttle = 0, brake = 0.7f, steering = 0, clutch = 0;
        int gear = phase >= 5 ? -1 : 1;
        if (phase == 1 || phase == 2 || phase == 3 || phase == 5) { throttle = 0.6f; brake = 0; clutch = 1; }
        if (phase == 2) { throttle = 0.5f; steering = 0.25f * sign; }
        if (phase == 3) { throttle = 0.5f; steering = -0.25f * sign; }
        if (phase == 5) throttle = -0.45f;
        transmission.Set(gear, clutch);
        if (tracked != nullptr) tracked->SetDriverInput(throttle, steering > 0 ? 0.75f : 1.0f, steering < 0 ? 0.75f : 1.0f, brake);
        else wheeled->SetDriverInput(throttle, steering, brake, 0);
        engineTorque = engine.GetTorque(std::abs(throttle));
        if (world.Update(1.0f / rate, 1, &allocator, &jobs) != JPH::EPhysicsUpdateError::None) return 4;
    }
    world.RemoveStepListener(vehicle); world.RemoveConstraint(vehicle); vehicle = nullptr;
    bodies.RemoveBody(chassis); bodies.DestroyBody(chassis); bodies.RemoveBody(ground); bodies.DestroyBody(ground);
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
    JPH::RegisterDefaultAllocator(); auto factory = std::make_unique<JPH::Factory>();
    JPH::Factory::sInstance = factory.get(); JPH::RegisterTypes(); std::cout.precision(9);
    int result = 0;
    for (int family : { 0, 1, 2 }) for (int detector : { 0, 1, 2 }) for (int sign : { -1, 1 }) for (int rate : { 60, 120 }) {
        if (result == 0) result = Physics3D::runDrive(family, detector, sign, rate);
    }
    JPH::UnregisterTypes(); JPH::Factory::sInstance = nullptr; return result;
}
