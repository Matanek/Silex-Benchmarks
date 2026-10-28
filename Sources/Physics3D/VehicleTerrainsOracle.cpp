#include <array>
#include <cstdlib>
#include <iostream>
#include <memory>
#include <Jolt/Jolt.h>
#include <Jolt/Physics/Collision/Shape/MeshShape.h>
#include <Jolt/Physics/Collision/Shape/HeightFieldShape.h>
#include <Jolt/Physics/Vehicle/MotorcycleController.h>
#include <Jolt/Physics/Vehicle/TrackedVehicleController.h>
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

void writeBody(JPH::BodyInterface& bodies, const JPH::BodyID& id) {
    writeVector(JPH::Vec3(bodies.GetPosition(id)));
    writeVector(bodies.GetLinearVelocity(id));
    const auto q = bodies.GetRotation(id);
    std::cout << ' ' << q.GetX() << ' ' << q.GetY() << ' ' << q.GetZ() << ' ' << q.GetW();
    writeVector(bodies.GetAngularVelocity(id));
}

// -----------------------------------------------------------------------------

JPH::RefConst<JPH::Shape> terrainShape(int terrain) {
    if (terrain == 3) {
        JPH::TriangleList triangles;
        triangles.emplace_back(JPH::Float3(-20, 0, -20), JPH::Float3(-20, 0, 20), JPH::Float3(20, 0, -20));
        triangles.emplace_back(JPH::Float3(20, 0, -20), JPH::Float3(-20, 0, 20), JPH::Float3(20, 0, 20));
        return JPH::MeshShapeSettings(triangles).Create().Get();
    }
    if (terrain == 4) {
        std::array<float, 16> heights {};
        return JPH::HeightFieldShapeSettings(heights.data(), JPH::Vec3::sZero(), JPH::Vec3(40.0f / 3, 1, 40.0f / 3), 4).Create().Get();
    }
    return new JPH::BoxShape(JPH::Vec3(terrain == 2 ? 10.25f : (terrain == 1 ? 100.0f : 20.0f), 0.5f, terrain == 1 ? 100.0f : 20.0f), 0);
}

// -----------------------------------------------------------------------------

int runTerrain(int family, int detector, int terrain, int rate, int motion) {
    JPH::BroadPhaseLayerInterfaceTable broadPhase(1, 1);
    broadPhase.MapObjectToBroadPhaseLayer(0, JPH::BroadPhaseLayer(0));
    JPH::ObjectLayerPairFilterTable pairFilter(1);
    pairFilter.EnableCollision(0, 0);
    JPH::ObjectVsBroadPhaseLayerFilterTable phaseFilter(broadPhase, 1, pairFilter, 1);
    JPH::PhysicsSystem world;
    world.Init(16, 0, 16, 16, broadPhase, phaseFilter, pairFilter);
    JPH::PhysicsSettings physics;
    physics.mNumVelocitySteps = 12;physics.mNumPositionSteps = 4;
    world.SetPhysicsSettings(physics);
    if (motion == 0 || terrain == 5) world.SetGravity(JPH::Vec3::sZero());
    auto& bodies = world.GetBodyInterface();
    const auto rotation = terrain == 1 ? JPH::Quat::sRotation(JPH::Vec3::sAxisX(), 0.15f) : JPH::Quat::sIdentity();
    JPH::Vec3 supportPosition(terrain == 2 ? -9.75f : 0, -0.5f, 0);
    if (terrain == 3) supportPosition = JPH::Vec3::sZero();
    if (terrain == 4) supportPosition = JPH::Vec3(-20, 0, -20);
    JPH::BodyCreationSettings supportSettings(terrainShape(terrain), JPH::RVec3(rotation * supportPosition), rotation, terrain == 5 ? JPH::EMotionType::Dynamic : JPH::EMotionType::Static, 0);
    supportSettings.mFriction = supportSettings.mLinearDamping = supportSettings.mAngularDamping = 0;
    supportSettings.mAllowSleeping = false;
    if (terrain == 5) {
        supportSettings.mOverrideMassProperties = JPH::EOverrideMassProperties::MassAndInertiaProvided;
        supportSettings.mMassPropertiesOverride.mMass = 1000;
        supportSettings.mMassPropertiesOverride.mInertia = JPH::Mat44::sScale(JPH::Vec3::sReplicate(10000));
    }
    const auto support = bodies.CreateAndAddBody(supportSettings, terrain == 5 ? JPH::EActivation::Activate : JPH::EActivation::DontActivate);
    JPH::Vec3 origin(terrain == 2 && family == 2 ? 0.6f : 0, motion == 1 ? (terrain == 5 ? 0.75f : 1.4f) : 0.8f, 0);
    JPH::RefConst<JPH::BoxShape> shape = new JPH::BoxShape(JPH::Vec3(0.7f, 0.2f, 1.2f), 0);
    JPH::BodyCreationSettings chassisSettings(shape, JPH::RVec3(rotation * origin), rotation, JPH::EMotionType::Dynamic, 0);
    chassisSettings.mLinearVelocity = rotation * JPH::Vec3(0, 0, motion == 1 ? 2.0f : 0);
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
    JPH::Ref<JPH::VehicleControllerSettings> controller;
    if (family == 1) {
        JPH::Ref<JPH::TrackedVehicleControllerSettings> tracks = new JPH::TrackedVehicleControllerSettings;
        tracks->mEngine.mMaxTorque = 0;
        tracks->mTransmission.mMode = JPH::ETransmissionMode::Manual;
        for (int i : { 0, 1 }) {
            tracks->mTracks[i].mDrivenWheel = 2 * i;
            tracks->mTracks[i].mWheels = { static_cast<JPH::uint>(2 * i), static_cast<JPH::uint>(2 * i + 1) };
            tracks->mTracks[i].mAngularDamping = 0;
        }
        controller = tracks.GetPtr();
    } else {
        JPH::Ref<JPH::WheeledVehicleControllerSettings> wheeled;
        if (family == 2) wheeled = new JPH::MotorcycleControllerSettings;
        else wheeled = new JPH::WheeledVehicleControllerSettings;
        wheeled->mEngine.mMaxTorque = 0;
        JPH::VehicleDifferentialSettings differential;
        differential.mLeftWheel = 0;differential.mRightWheel = 1;
        wheeled->mDifferentials.push_back(differential);
        controller = wheeled.GetPtr();
    }
    settings.mController = controller;
    const int wheelCount = family == 2 ? 2 : 4;
    for (int index = 0; index < wheelCount; ++index) {
        JPH::Ref<JPH::WheelSettings> wheel;
        if (family == 1) {
            JPH::Ref<JPH::WheelSettingsTV> tracked = new JPH::WheelSettingsTV;
            tracked->mLongitudinalFriction = tracked->mLateralFriction = 0;
            wheel = tracked.GetPtr();
        } else {
            JPH::Ref<JPH::WheelSettingsWV> wheeled = new JPH::WheelSettingsWV;
            wheeled->mLongitudinalFriction.Clear();wheeled->mLongitudinalFriction.AddPoint(0, 0);
            wheeled->mLateralFriction.Clear();wheeled->mLateralFriction.AddPoint(0, 0);
            wheeled->mAngularDamping = 0;
            wheel = wheeled.GetPtr();
        }
        wheel->mPosition = JPH::Vec3(family == 2 ? 0 : (index < 2 ? -0.6f : 0.6f), 0, family == 2 ? (index == 0 ? 1.0f : -1.0f) : (index % 2 == 0 ? -1.0f : 1.0f));
        wheel->mRadius = 0.3f;wheel->mWidth = 0.4f;
        wheel->mSuspensionMinLength = 0.2f;wheel->mSuspensionMaxLength = 0.6f;
        wheel->mSuspensionSpring = JPH::SpringSettings(JPH::ESpringMode::StiffnessAndDamping, 10000, 1000);
        settings.mWheels.push_back(wheel.GetPtr());
    }
    JPH::Ref<JPH::VehicleConstraint> vehicle = new JPH::VehicleConstraint(*chassisBody, settings);
    if (detector == 0) vehicle->SetVehicleCollisionTester(new JPH::VehicleCollisionTesterRay(0));
    else if (detector == 1) vehicle->SetVehicleCollisionTester(new JPH::VehicleCollisionTesterCastSphere(0, 0.3f));
    else vehicle->SetVehicleCollisionTester(new JPH::VehicleCollisionTesterCastCylinder(0, 0));
    if (family == 1) static_cast<JPH::TrackedVehicleController*>(vehicle->GetController())->GetTransmission().Set(0, 1);
    if (family == 2) static_cast<JPH::MotorcycleController*>(vehicle->GetController())->EnableLeanController(false);
    world.AddConstraint(vehicle);world.AddStepListener(vehicle);
    JPH::TempAllocatorImpl allocator(1024 * 1024);
    JPH::JobSystemSingleThreaded jobs(JPH::cMaxPhysicsJobs);
    const int last = motion == 0 ? 1 : 6 * rate;
    for (int step = 0; step <= last; ++step) {
        std::cout << "terrain-body " << family << ' ' << detector << ' ' << terrain << ' ' << rate << ' ' << motion << ' ' << step;
        writeBody(bodies, chassis);writeBody(bodies, support);std::cout << '\n';
        for (int index = 0; index < wheelCount; ++index) {
            const auto* wheel = vehicle->GetWheel(index);
            const bool touching = wheel->HasContact();
            std::cout << "terrain-wheel " << family << ' ' << detector << ' ' << terrain << ' ' << rate << ' ' << motion << ' ' << step << ' ' << index;
            std::cout << ' ' << wheel->GetSuspensionLength() << ' ' << wheel->GetSuspensionLambda() * rate << ' ' << touching;
            writeVector(touching ? JPH::Vec3(wheel->GetContactPosition()) : JPH::Vec3::sZero());
            writeVector(touching ? wheel->GetContactNormal() : JPH::Vec3::sZero());std::cout << '\n';
        }
        if (step == last) break;
        if (world.Update(1.0f / rate, 1, &allocator, &jobs) != JPH::EPhysicsUpdateError::None) return 4;
    }
    world.RemoveStepListener(vehicle);world.RemoveConstraint(vehicle);vehicle = nullptr;
    bodies.RemoveBody(chassis);bodies.DestroyBody(chassis);bodies.RemoveBody(support);bodies.DestroyBody(support);
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
    for (int family : { 0, 1, 2 }) for (int detector : { 0, 1, 2 }) for (int terrain : { 0, 1, 2, 3, 4, 5 }) for (int rate : { 60, 120 }) {
        if (result == 0) result = Physics3D::runTerrain(family, detector, terrain, rate, 0);
        if (result == 0 && terrain != 2) result = Physics3D::runTerrain(family, detector, terrain, rate, 1);
    }
    JPH::UnregisterTypes();
    JPH::Factory::sInstance = nullptr;
    return result;
}
