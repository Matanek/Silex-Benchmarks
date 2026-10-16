#include <array>
#include <cstdlib>
#include <iostream>
#include <memory>
#include <vector>
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

#include <Jolt/Physics/Collision/Shape/CapsuleShape.h>
#include <Jolt/Physics/Collision/Shape/PlaneShape.h>
#include <Jolt/Physics/Collision/Shape/StaticCompoundShape.h>
namespace Physics3D {

// -----------------------------------------------------------------------------

void writeVector(JPH::Vec3Arg value) {
    std::cout << ' ' << value.GetX() << ' ' << value.GetY() << ' ' << value.GetZ();
}

// -----------------------------------------------------------------------------

int runContact(int kind, int rate) {
    JPH::BroadPhaseLayerInterfaceTable broadPhase(2, 1);
    broadPhase.MapObjectToBroadPhaseLayer(0, JPH::BroadPhaseLayer(0));
    broadPhase.MapObjectToBroadPhaseLayer(1, JPH::BroadPhaseLayer(0));
    JPH::ObjectLayerPairFilterTable pairFilter(2);
    pairFilter.EnableCollision(0, 0);
    JPH::ObjectVsBroadPhaseLayerFilterTable phaseFilter(broadPhase, 1, pairFilter, 2);
    JPH::PhysicsSystem world;
    world.Init(16, 0, 16, 16, broadPhase, phaseFilter, pairFilter);
    auto& bodies = world.GetBodyInterface();
    std::vector<JPH::BodyID> targets;
    const auto ground = [&](const JPH::Shape* shape, JPH::Vec3Arg position = JPH::Vec3::sZero(),
                            JPH::QuatArg rotation = JPH::Quat::sIdentity(), bool sensor = false, bool excluded = false) {
        JPH::BodyCreationSettings config(shape, JPH::RVec3(position), rotation, JPH::EMotionType::Static, excluded ? 1 : 0);
        config.mIsSensor = sensor;
        const auto id = bodies.CreateAndAddBody(config, JPH::EActivation::DontActivate);
        targets.push_back(id);
        return id;
    };
    JPH::RefConst<JPH::BoxShape> edge = new JPH::BoxShape(JPH::Vec3(0.5f, 0.05f, 1), 0);
    JPH::RefConst<JPH::BoxShape> wide = new JPH::BoxShape(JPH::Vec3(2.5f, 0.05f, 2.5f), 0);
    JPH::Vec3 origin(0, 0.8f, 0);
    float radius = 0.3f;
    if (kind == 0 || kind == 16 || kind == 17) {
        ground(wide, JPH::Vec3(0, -0.05f, 0));
        if (kind == 16) radius = 0.4f;
        if (kind == 17) origin.SetY(1.2f);
    } else if (kind == 18) {
        const auto rotation = JPH::Quat::sRotation(JPH::Vec3::sAxisZ(), JPH::DegreesToRadians(20.0f));
        ground(new JPH::BoxShape(JPH::Vec3(10, 0.5f, 10), 0), rotation * JPH::Vec3(0, -0.5f, 0), rotation);
    } else if (kind == 1) {
        ground(new JPH::PlaneShape(JPH::Plane(JPH::Vec3::sAxisY(), 0)), JPH::Vec3::sZero(),
               JPH::Quat::sRotation(JPH::Vec3::sAxisZ(), JPH::DegreesToRadians(20.0f)));
    } else if (kind == 2 || kind == 4 || kind == 5 || kind == 14 || kind == 15) {
        origin = JPH::Vec3(0.7f, 0.75f, 0);
        if (kind == 4) radius = 0.1f;
        if (kind == 5) origin = JPH::Vec3(0.79f, 0.6f, 0);
        auto rotation = JPH::Quat::sIdentity();
        if (kind == 15) {
            rotation = JPH::Quat::sRotation(JPH::Vec3::sAxisY(), 0.4f);
            origin = rotation * origin;
        }
        ground(edge, JPH::Vec3(0, -0.05f, 0), rotation);
        if (kind == 5) ground(wide, JPH::Vec3(0, -0.2f, 0));
    } else if (kind == 3) {
        origin = JPH::Vec3(0.65f, 0.75f, 0.65f);
        ground(new JPH::BoxShape(JPH::Vec3(0.5f, 0.05f, 0.5f), 0), JPH::Vec3(0, -0.05f, 0));
    } else if (kind == 6) {
        origin = JPH::Vec3(0.5f, 0.8f, 0);
        ground(new JPH::SphereShape(0.4f));
    } else if (kind == 7) {
        origin = JPH::Vec3(0.3f, 0.9f, 0);
        radius = 0.2f;
        ground(new JPH::CapsuleShape(0.3f, 0.3f));
    } else if (kind == 8 || kind == 13) {
        origin = JPH::Vec3(0.79f, 0.6f, 0);
        JPH::StaticCompoundShapeSettings compound;
        if (kind == 13) {
            origin = JPH::Vec3(0, 0.2f, 0);
            compound.AddShape(JPH::Vec3(0, -0.05f, 0), JPH::Quat::sIdentity(), wide);
            compound.AddShape(JPH::Vec3(0, 0.05f, 0), JPH::Quat::sIdentity(), wide);
        } else {
            compound.AddShape(JPH::Vec3(0, -0.05f, 0), JPH::Quat::sIdentity(), edge);
            compound.AddShape(JPH::Vec3(0, -0.2f, 0), JPH::Quat::sIdentity(), wide);
        }
        const auto result = compound.Create();
        if (result.HasError()) return 3;
        ground(result.Get());
    } else if (kind == 9 || kind == 10 || kind == 11 || kind == 12) {
        ground(wide, JPH::Vec3(0, -0.05f, 0));
        ground(wide, JPH::Vec3(0, 0.05f, 0), JPH::Quat::sIdentity(), kind == 9, kind == 10);
        if (kind == 11) bodies.RemoveBody(targets[1]);
        if (kind == 12) origin.SetY(0.2f);
    }
    JPH::RefConst<JPH::SphereShape> shape = new JPH::SphereShape(0.01f);
    JPH::BodyCreationSettings config(shape, JPH::RVec3(origin), JPH::Quat::sIdentity(), JPH::EMotionType::Dynamic, 0);
    auto* chassisBody = bodies.CreateBody(config);
    if (chassisBody == nullptr) return 4;
    const auto chassis = chassisBody->GetID();
    bodies.AddBody(chassis, JPH::EActivation::Activate);
    JPH::VehicleConstraintSettings settings;
    JPH::Ref<JPH::WheeledVehicleControllerSettings> controller = new JPH::WheeledVehicleControllerSettings;
    controller->mEngine.mMaxTorque = 0;
    JPH::VehicleDifferentialSettings differential;
    differential.mLeftWheel = 0;
    differential.mRightWheel = -1;
    controller->mDifferentials.push_back(differential);
    settings.mController = controller;
    JPH::Ref<JPH::WheelSettingsWV> wheel = new JPH::WheelSettingsWV;
    wheel->mPosition = JPH::Vec3::sZero();
    wheel->mRadius = 0.3f;
    wheel->mSuspensionMinLength = 0.2f;
    wheel->mSuspensionMaxLength = 0.6f;
    settings.mWheels.push_back(wheel.GetPtr());
    JPH::Ref<JPH::VehicleConstraint> vehicle = new JPH::VehicleConstraint(*chassisBody, settings);
    JPH::Ref<JPH::VehicleCollisionTester> tester;
    if (kind == 14) tester = new JPH::VehicleCollisionTesterRay(0, JPH::Vec3::sAxisY(), JPH::DegreesToRadians(60.0f));
    else tester = new JPH::VehicleCollisionTesterCastSphere(0, radius, JPH::Vec3::sAxisY(), JPH::DegreesToRadians(60.0f));
    JPH::Body* support = nullptr;
    JPH::SubShapeID child;
    JPH::RVec3 point = JPH::RVec3::sZero();
    JPH::Vec3 normal = JPH::Vec3::sZero();
    float length = 0.6f;
    const bool contact = tester->Collide(world, *vehicle, 0, JPH::RVec3(origin), -JPH::Vec3::sAxisY(),
                                         chassis, support, child, point, normal, length);
    int label = 0;
    if (contact) for (std::size_t index = 0; index < targets.size(); ++index) {
        if (support->GetID() == targets[index]) label = static_cast<int>(index) + 1;
    }
    std::cout << "sphere_contact " << kind << ' ' << rate << " 0 " << contact << ' ' << length;
    writeVector(JPH::Vec3(point));
    writeVector(normal);
    std::cout << ' ' << label << '\n';
    vehicle = nullptr;
    bodies.RemoveBody(chassis);
    bodies.DestroyBody(chassis);
    for (std::size_t index = 0; index < targets.size(); ++index) {
        if (!(kind == 11 && index == 1)) bodies.RemoveBody(targets[index]);
        bodies.DestroyBody(targets[index]);
    }
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
    for (int kind = 0; kind < 19; ++kind) for (int rate : { 60, 120 }) {
        if (result == 0) result = Physics3D::runContact(kind, rate);
    }
    JPH::UnregisterTypes();
    JPH::Factory::sInstance = nullptr;
    return result;
}
