#include <iostream>
#include <memory>
#include <string_view>
#include <Jolt/Jolt.h>
#include <Jolt/ConfigurationString.h>
#include <Jolt/Core/Factory.h>
#include <Jolt/Core/JobSystemSingleThreaded.h>
#include <Jolt/Core/TempAllocator.h>
#include <Jolt/RegisterTypes.h>
#include <Jolt/Physics/PhysicsSystem.h>
#include <Jolt/Physics/Body/BodyCreationSettings.h>
#include <Jolt/Physics/Body/BodyLock.h>
#include <Jolt/Physics/Character/Character.h>
#include <Jolt/Physics/Character/CharacterVirtual.h>
#include <Jolt/Physics/Collision/BroadPhase/BroadPhaseLayerInterfaceTable.h>
#include <Jolt/Physics/Collision/BroadPhase/ObjectVsBroadPhaseLayerFilterTable.h>
#include <Jolt/Physics/Collision/ObjectLayerPairFilterTable.h>
#include <Jolt/Physics/Collision/Shape/BoxShape.h>
#include <Jolt/Physics/Collision/Shape/CapsuleShape.h>
#include <Jolt/Physics/Collision/Shape/SphereShape.h>

namespace CharacterQualification {

// -----------------------------------------------------------------------------

class World {
    private: JPH::BroadPhaseLayerInterfaceTable broadPhase { 1, 1 };
    private: JPH::ObjectLayerPairFilterTable pairFilter { 1 };
    private: std::unique_ptr<JPH::ObjectVsBroadPhaseLayerFilterTable> phaseFilter;
    public: JPH::PhysicsSystem physics;
    public: JPH::TempAllocatorImpl allocator { 1024 * 1024 };
    public: JPH::JobSystemSingleThreaded jobs { JPH::cMaxPhysicsJobs };
    public: World() {
        broadPhase.MapObjectToBroadPhaseLayer(0, JPH::BroadPhaseLayer(0));
        pairFilter.EnableCollision(0, 0);
        phaseFilter = std::make_unique<JPH::ObjectVsBroadPhaseLayerFilterTable>(broadPhase, 1, pairFilter, 1);
        physics.Init(32, 0, 64, 64, broadPhase, *phaseFilter, pairFilter);
        physics.SetGravity(JPH::Vec3::sZero());
        auto settings = physics.GetPhysicsSettings();
        settings.mPenetrationSlop = 0.001f;
        settings.mNumVelocitySteps = 12;
        settings.mNumPositionSteps = 4;
        physics.SetPhysicsSettings(settings);
    }
    public: JPH::BodyID add(const JPH::Shape* shape, JPH::RVec3Arg position,
        JPH::EMotionType type, float mass = 10.0f) {
        JPH::BodyCreationSettings settings(shape, position, JPH::Quat::sIdentity(), type, 0);
        settings.mFriction = 0.0f;
        settings.mLinearDamping = 0.0f;
        settings.mAngularDamping = 0.0f;
        settings.mAllowSleeping = false;
        if (type == JPH::EMotionType::Dynamic) {
            settings.mOverrideMassProperties = JPH::EOverrideMassProperties::MassAndInertiaProvided;
            settings.mMassPropertiesOverride.mMass = mass;
            settings.mMassPropertiesOverride.mInertia = JPH::Mat44::sScale(JPH::Vec3::sReplicate(1.0f));
        }
        return physics.GetBodyInterface().CreateAndAddBody(settings,
            type == JPH::EMotionType::Static ? JPH::EActivation::DontActivate : JPH::EActivation::Activate);
    }
    public: void step(float delta) {
        if (physics.Update(delta, 1, &allocator, &jobs) != JPH::EPhysicsUpdateError::None) std::terminate();
    }
    public: void removeDamping(JPH::BodyID body) {
        JPH::BodyLockWrite lock(physics.GetBodyLockInterface(), body);
        if (!lock.Succeeded()) std::terminate();
        lock.GetBody().GetMotionProperties()->SetLinearDamping(0.0f);
        lock.GetBody().GetMotionProperties()->SetAngularDamping(0.0f);
        lock.GetBody().SetAllowSleeping(false);
    }
};

// -----------------------------------------------------------------------------

JPH::CharacterVirtualSettings virtualSettings() {
    JPH::CharacterVirtualSettings settings;
    settings.mShape = new JPH::CapsuleShape(0.55f, 0.3f);
    settings.mCharacterPadding = 0.002f;
    settings.mMass = 70.0f;
    settings.mMaxStrength = 100.0f;
    settings.mSupportingVolume = JPH::Plane(JPH::Vec3::sAxisY(), -0.55f);
    return settings;
}

void virtualPush(float start, float velocity, std::string_view label) {
    World world;
    const auto ball = world.add(new JPH::SphereShape(0.5f), JPH::RVec3(1.0f, 0.852f, 0.0f), JPH::EMotionType::Dynamic);
    const auto settings = virtualSettings();
    JPH::CharacterVirtual actor(&settings, JPH::RVec3(start, 0.852f, 0.0f), JPH::Quat::sIdentity(), &world.physics);
    actor.SetLinearVelocity(JPH::Vec3(velocity, 0.0f, 0.0f));
    actor.Update(0.1f, JPH::Vec3::sZero(), world.physics.GetDefaultBroadPhaseLayerFilter(0),
        world.physics.GetDefaultLayerFilter(0), {}, {}, world.allocator);
    std::cout << label << "_vx=" << world.physics.GetBodyInterface().GetLinearVelocity(ball).GetX() << '\n';
    std::cout << label << "_spin=" << world.physics.GetBodyInterface().GetAngularVelocity(ball).Length() << '\n';
}

void virtualWeight() {
    World world;
    const auto platform = world.add(new JPH::BoxShape(JPH::Vec3(3.0f, 0.1f, 3.0f), 0.0f),
        JPH::RVec3(0.0f, -0.1f, 0.0f), JPH::EMotionType::Dynamic);
    const auto settings = virtualSettings();
    JPH::CharacterVirtual actor(&settings, JPH::RVec3(0.0f, 0.852f, 0.0f), JPH::Quat::sIdentity(), &world.physics);
    actor.SetLinearVelocity(JPH::Vec3(0.0f, -0.3f, 0.0f));
    actor.Update(1.0f / 60.0f, JPH::Vec3(0.0f, -9.81f, 0.0f), world.physics.GetDefaultBroadPhaseLayerFilter(0),
        world.physics.GetDefaultLayerFilter(0), {}, {}, world.allocator);
    std::cout << "weight_vy=" << world.physics.GetBodyInterface().GetLinearVelocity(platform).GetY() << '\n';
}

// -----------------------------------------------------------------------------

JPH::CharacterSettings physicalSettings(float halfHeight = 0.55f) {
    JPH::CharacterSettings settings;
    settings.mShape = new JPH::CapsuleShape(halfHeight, 0.3f);
    settings.mMass = 70.0f;
    settings.mFriction = 0.0f;
    settings.mSupportingVolume = JPH::Plane(JPH::Vec3::sAxisY(), -halfHeight);
    return settings;
}

void physicalCollision() {
    World world;
    const auto settings = physicalSettings();
    JPH::Character actor(&settings, JPH::RVec3(-0.6f, 0.0f, 0.0f), JPH::Quat::sIdentity(), 0, &world.physics);
    actor.AddToPhysicsSystem();
    world.removeDamping(actor.GetBodyID());
    auto& bodies = world.physics.GetBodyInterface();
    bodies.SetLinearAndAngularVelocity(actor.GetBodyID(), JPH::Vec3::sAxisX(), JPH::Vec3::sZero());
    const auto ball = world.add(new JPH::SphereShape(0.3f), JPH::RVec3::sZero(), JPH::EMotionType::Dynamic, 30.0f);
    world.step(0.01f);
    actor.PostSimulation(0.02f);
    std::cout << "physical_vx=" << actor.GetLinearVelocity().GetX() << '\n';
    std::cout << "physical_body_vx=" << bodies.GetLinearVelocity(ball).GetX() << '\n';
    std::cout << "physical_spin=" << bodies.GetAngularVelocity(actor.GetBodyID()).Length() << '\n';
    actor.RemoveFromPhysicsSystem();
}

void physicalRest() {
    World world;
    world.physics.SetGravity(JPH::Vec3(0.0f, -9.81f, 0.0f));
    world.add(new JPH::BoxShape(JPH::Vec3(10.0f, 0.1f, 10.0f), 0.0f),
        JPH::RVec3(0.0f, -0.1f, 0.0f), JPH::EMotionType::Static);
    const auto settings = physicalSettings();
    JPH::Character actor(&settings, JPH::RVec3(0.0f, 1.2f, 0.0f), JPH::Quat::sIdentity(), 0, &world.physics);
    actor.AddToPhysicsSystem();
    world.removeDamping(actor.GetBodyID());
    for (int step = 0; step < 180; ++step) { world.step(1.0f / 120.0f); actor.PostSimulation(0.02f); }
    std::cout << "rest_y=" << actor.GetPosition().GetY() << '\n';
    std::cout << "rest_vy=" << actor.GetLinearVelocity().GetY() << '\n';
    std::cout << "rest_normal_y=" << actor.GetGroundNormal().GetY() << '\n';
    actor.RemoveFromPhysicsSystem();
}

void resize() {
    World world;
    const auto ceiling = world.add(new JPH::BoxShape(JPH::Vec3(2.0f, 0.1f, 2.0f), 0.0f),
        JPH::RVec3(0.0f, 1.1f, 0.0f), JPH::EMotionType::Static);
    const auto settings = physicalSettings(0.15f);
    JPH::Character actor(&settings, JPH::RVec3(0.0f, 0.452f, 0.0f), JPH::Quat::sIdentity(), 0, &world.physics);
    actor.AddToPhysicsSystem();
    JPH::RefConst<JPH::Shape> standing = new JPH::CapsuleShape(0.55f, 0.3f);
    actor.SetPosition(JPH::RVec3(0.0f, 0.852f, 0.0f));
    const bool blocked = !actor.SetShape(standing, 0.005f);
    actor.SetPosition(JPH::RVec3(0.0f, 0.452f, 0.0f));
    std::cout << "resize_blocked=" << blocked << '\n';
    auto& bodies = world.physics.GetBodyInterface();
    bodies.RemoveBody(ceiling); bodies.DestroyBody(ceiling);
    actor.SetPosition(JPH::RVec3(0.0f, 0.852f, 0.0f));
    if (!actor.SetShape(standing, 0.005f)) std::terminate();
    std::cout << "resize_feet=" << actor.GetPosition().GetY() - 0.85f << '\n';
    std::cout << "resize_mass=" << actor.GetCharacterSettings().mMass << '\n';
    actor.RemoveFromPhysicsSystem();
}

// -----------------------------------------------------------------------------

} // namespace CharacterQualification

int main(int count, char** values) {
    if (count == 2 && std::string_view(values[1]) == "--configuration") {
        std::cout << JPH::GetConfigurationString() << '\n'; return 0;
    }
    if (count != 1) return 2;
    JPH::RegisterDefaultAllocator();
    JPH::Factory::sInstance = new JPH::Factory();
    JPH::RegisterTypes();
    std::cout.precision(9);
    CharacterQualification::virtualPush(0.198f, 0.01f, "weak");
    CharacterQualification::virtualPush(0.0f, 10.0f, "capped");
    CharacterQualification::virtualWeight();
    CharacterQualification::physicalCollision();
    CharacterQualification::physicalRest();
    CharacterQualification::resize();
    JPH::UnregisterTypes();
    delete JPH::Factory::sInstance;
    JPH::Factory::sInstance = nullptr;
}
