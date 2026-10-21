#include <cfloat>
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
#include <Jolt/Physics/Vehicle/WheeledVehicleController.h>

namespace Physics3D {

// -----------------------------------------------------------------------------

void writeVector(JPH::Vec3Arg value) {
    std::cout << ' ' << value.GetX() << ' ' << value.GetY() << ' ' << value.GetZ();
}

// -----------------------------------------------------------------------------

int runIncline(int sign, int contact, int grip, int rate, bool soft) {
    const auto rotation = JPH::Quat::sRotation(JPH::Vec3::sAxisX(), -0.2f * sign);
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
    JPH::RefConst<JPH::PlaneShape> floorShape = new JPH::PlaneShape(JPH::Plane(rotation * JPH::Vec3::sAxisY(), 0));
    JPH::BodyCreationSettings floorSettings(floorShape, JPH::RVec3::sZero(), JPH::Quat::sIdentity(), JPH::EMotionType::Static, 0);
    floorSettings.mFriction = 1;
    const auto floor = bodies.CreateAndAddBody(floorSettings, JPH::EActivation::DontActivate);
    JPH::RefConst<JPH::BoxShape> shape = new JPH::BoxShape(JPH::Vec3(0.7f, 0.2f, 1.2f));
    JPH::BodyCreationSettings chassisSettings(shape, JPH::RVec3(rotation * JPH::Vec3(0, 1.15f, 0)), rotation, JPH::EMotionType::Dynamic, 0);
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
    controller->mEngine.mMaxTorque = 40;
    controller->mEngine.mMinRPM = 0;
    controller->mEngine.mMaxRPM = 6000;
    controller->mEngine.mAngularDamping = 0;
    controller->mEngine.mNormalizedTorque.Clear();
    controller->mEngine.mNormalizedTorque.AddPoint(0, 1);
    controller->mTransmission.mMode = JPH::ETransmissionMode::Manual;
    controller->mTransmission.mGearRatios = { 1.0f };
    controller->mTransmission.mReverseGearRatios = { -1.0f };
    controller->mDifferentialLimitedSlipRatio = FLT_MAX;
    for (int index : { 0, 1 }) {
        JPH::VehicleDifferentialSettings differential;
        differential.mLeftWheel = index;
        differential.mRightWheel = index + 2;
        differential.mDifferentialRatio = 3;
        differential.mLeftRightSplit = 0.5f;
        differential.mEngineTorqueRatio = 0.5f;
        differential.mLimitedSlipRatio = FLT_MAX;
        controller->mDifferentials.push_back(differential);
    }
    settings.mController = controller;
    for (float x : { -0.6f, 0.6f }) for (float z : { -1.0f, 1.0f }) {
        JPH::Ref<JPH::WheelSettingsWV> wheel = new JPH::WheelSettingsWV;
        wheel->mPosition = JPH::Vec3(x, 0, z);
        wheel->mRadius = 0.3f;
        wheel->mWidth = 0.4f;
        wheel->mSuspensionMinLength = 0.2f;
        wheel->mSuspensionMaxLength = soft ? 0.77985f : 0.6f;
        wheel->mSuspensionSpring = JPH::SpringSettings(JPH::ESpringMode::StiffnessAndDamping, soft ? 1200.0f : 10000.0f, soft ? 160.0f : 1000.0f);
        wheel->mAngularDamping = 0;
        wheel->mMaxSteerAngle = 0;
        wheel->mMaxBrakeTorque = 1500;
        wheel->mMaxHandBrakeTorque = 0;
        wheel->mLongitudinalFriction.Clear();
        wheel->mLongitudinalFriction.AddPoint(0, static_cast<float>(grip));
        wheel->mLateralFriction.Clear();
        wheel->mLateralFriction.AddPoint(0, static_cast<float>(grip));
        settings.mWheels.push_back(wheel.GetPtr());
    }
    JPH::Ref<JPH::VehicleConstraint> vehicle = new JPH::VehicleConstraint(*chassisBody, settings);
    if (contact == 0) vehicle->SetVehicleCollisionTester(new JPH::VehicleCollisionTesterRay(0));
    if (contact == 1) vehicle->SetVehicleCollisionTester(new JPH::VehicleCollisionTesterCastSphere(0, 0.3f, JPH::Vec3::sAxisY(), JPH::DegreesToRadians(60.0f)));
    if (contact == 2) vehicle->SetVehicleCollisionTester(new JPH::VehicleCollisionTesterCastCylinder(0, 0.0f));
    auto* driver = static_cast<JPH::WheeledVehicleController*>(vehicle->GetController());
    driver->GetTransmission().Set(sign, 1);
    world.AddConstraint(vehicle);
    world.AddStepListener(vehicle);
    JPH::TempAllocatorImpl allocator(1024 * 1024);
    JPH::JobSystemSingleThreaded jobs(JPH::cMaxPhysicsJobs);
    for (int step = 0; step <= rate * 8; ++step) {
        std::cout << (soft ? "incline-soft " : "incline ") << sign << ' ' << contact << ' ' << grip << ' ' << rate << ' ' << step;
        writeVector(JPH::Vec3(bodies.GetPosition(chassis)));
        writeVector(bodies.GetLinearVelocity(chassis));
        const auto q = bodies.GetRotation(chassis);
        std::cout << ' ' << q.GetX() << ' ' << q.GetY() << ' ' << q.GetZ() << ' ' << q.GetW();
        writeVector(bodies.GetAngularVelocity(chassis));
        for (int index = 0; index < 4; ++index) {
            const auto* wheel = static_cast<const JPH::WheelWV*>(vehicle->GetWheel(index));
            std::cout << ' ' << wheel->GetSuspensionLength() << ' ' << wheel->GetSuspensionLambda() * rate << ' ' << wheel->GetAngularVelocity() << ' ' << wheel->GetRotationAngle() << ' ' << wheel->GetLongitudinalLambda() * rate << ' ' << wheel->GetLateralLambda() * rate << ' ' << wheel->HasContact();
            const bool touching = wheel->HasContact();
            writeVector(touching ? JPH::Vec3(wheel->GetContactPosition()) : JPH::Vec3::sZero());
            writeVector(touching ? wheel->GetContactNormal() : JPH::Vec3::sZero());
            writeVector(touching ? wheel->GetContactLongitudinal() : JPH::Vec3::sZero());
        }
        std::cout << ' ' << driver->GetEngine().GetCurrentRPM() << ' ' << driver->GetTransmission().GetCurrentGear() << ' ' << driver->GetTransmission().GetClutchFriction() << '\n';
        if (step == rate * 8) break;
        const bool driving = step >= rate * 2 && step < rate * 5;
        driver->SetDriverInput(driving ? 0.8f * sign : 0.0f, 0, driving ? 0.0f : 1.0f, 0);
        if (world.Update(1.0f / rate, 1, &allocator, &jobs) != JPH::EPhysicsUpdateError::None) return 4;
    }
    world.RemoveStepListener(vehicle);
    world.RemoveConstraint(vehicle);
    vehicle = nullptr;
    bodies.RemoveBody(chassis);
    bodies.DestroyBody(chassis);
    bodies.RemoveBody(floor);
    bodies.DestroyBody(floor);
    return 0;
}

// -----------------------------------------------------------------------------

} // namespace Physics3D

int main(int argc, char** argv) {
    if (argc > 2 || (argc == 2 && std::string_view(argv[1]) != "--soft")) return 2;
    const bool soft = argc == 2;
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
    for (int sign : { -1, 1 }) for (int contact : { 0, 1, 2 }) for (int grip : { 0, 1 }) for (int rate : { 60, 120 }) {
        if (result == 0) result = Physics3D::runIncline(sign, contact, grip, rate, soft);
    }
    JPH::UnregisterTypes();
    JPH::Factory::sInstance = nullptr;
    return result;
}
