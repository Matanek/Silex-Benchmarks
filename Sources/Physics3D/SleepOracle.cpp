#include <Jolt/Jolt.h>
#include <Jolt/ConfigurationString.h>
#include <Jolt/RegisterTypes.h>
#include <Jolt/Core/Factory.h>
#include <Jolt/Core/JobSystemSingleThreaded.h>
#include <Jolt/Core/TempAllocator.h>
#include <Jolt/Physics/PhysicsSystem.h>
#include <Jolt/Physics/Body/BodyCreationSettings.h>
#include <Jolt/Physics/Collision/BroadPhase/BroadPhaseLayerInterfaceTable.h>
#include <Jolt/Physics/Collision/BroadPhase/ObjectVsBroadPhaseLayerFilterTable.h>
#include <Jolt/Physics/Collision/ObjectLayerPairFilterTable.h>
#include <Jolt/Physics/Collision/Shape/SphereShape.h>
#include <iostream>
#include <string_view>

namespace Physics3D {

int run() {
    JPH::RegisterDefaultAllocator();
    JPH::Factory::sInstance = new JPH::Factory();
    JPH::RegisterTypes();

    JPH::BroadPhaseLayerInterfaceTable broadPhase(1, 1);
    broadPhase.MapObjectToBroadPhaseLayer(0, JPH::BroadPhaseLayer(0));
    JPH::ObjectLayerPairFilterTable pairFilter(1);
    pairFilter.EnableCollision(0, 0);
    JPH::ObjectVsBroadPhaseLayerFilterTable phaseFilter(broadPhase, 1, pairFilter, 1);

    JPH::PhysicsSystem world;
    world.Init(16, 0, 16, 16, broadPhase, phaseFilter, pairFilter);
    world.SetGravity(JPH::Vec3::sZero());
    JPH::RefConst<JPH::SphereShape> sphere = new JPH::SphereShape(0.5f);
    JPH::BodyCreationSettings settings(
        sphere, JPH::RVec3::sZero(), JPH::Quat::sIdentity(),
        JPH::EMotionType::Dynamic, 0
    );
    settings.mLinearDamping = 0.0f;
    settings.mAngularDamping = 0.0f;
    auto& bodies = world.GetBodyInterface();
    const auto body = bodies.CreateAndAddBody(settings, JPH::EActivation::Activate);
    if (body.IsInvalid()) return 3;

    JPH::TempAllocatorImpl allocator(1024 * 1024);
    JPH::JobSystemSingleThreaded jobs(JPH::cMaxPhysicsJobs);
    constexpr auto delta = 1.0f / 60.0f;
    auto sleepStep = 0;
    for (auto step = 1; step <= 120; ++step) {
        if (world.Update(delta, 1, &allocator, &jobs) != JPH::EPhysicsUpdateError::None) {
            return 4;
        }
        if (sleepStep == 0 && !bodies.IsActive(body)) sleepStep = step;
    }
    bodies.SetLinearVelocity(body, JPH::Vec3(1.0f, 0.0f, 0.0f));
    const auto activeAfterCommand = bodies.IsActive(body);
    if (world.Update(delta, 1, &allocator, &jobs) != JPH::EPhysicsUpdateError::None) {
        return 5;
    }

    std::cout.precision(9);
    std::cout << "sleep_step=" << sleepStep << '\n'
              << "awake_after_command=" << (activeAfterCommand ? 1 : 0) << '\n'
              << "velocity_after_wake=" << bodies.GetLinearVelocity(body).GetX() << '\n';

    bodies.RemoveBody(body);
    bodies.DestroyBody(body);
    JPH::UnregisterTypes();
    delete JPH::Factory::sInstance;
    JPH::Factory::sInstance = nullptr;
    return 0;
}

} // namespace Physics3D

int main(int count, char** values) {
    if (count == 2 && std::string_view(values[1]) == "--configuration") {
        std::cout << JPH::GetConfigurationString() << '\n';
        return 0;
    }
    if (count != 1) return 2;
    return Physics3D::run();
}
