#include <Jolt/Jolt.h>
#include <Jolt/ConfigurationString.h>
#include <Jolt/RegisterTypes.h>
#include <Jolt/Core/Factory.h>
#include <Jolt/Physics/PhysicsSystem.h>
#include <Jolt/Physics/Body/BodyCreationSettings.h>
#include <Jolt/Physics/Collision/BroadPhase/BroadPhaseLayerInterfaceTable.h>
#include <Jolt/Physics/Collision/BroadPhase/ObjectVsBroadPhaseLayerFilterTable.h>
#include <Jolt/Physics/Collision/ObjectLayerPairFilterTable.h>
#include <Jolt/Physics/Collision/Shape/SphereShape.h>
#include <Jolt/Physics/Collision/NarrowPhaseQuery.h>
#include <Jolt/Physics/Collision/CastResult.h>
#include <Jolt/Physics/Collision/RayCast.h>
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
    JPH::RefConst<JPH::SphereShape> sphere = new JPH::SphereShape(0.5f);
    JPH::BodyCreationSettings farSettings(
        sphere, JPH::RVec3(4.0f, 0.0f, 0.0f), JPH::Quat::sIdentity(),
        JPH::EMotionType::Static, 0
    );
    JPH::BodyCreationSettings nearSettings(
        sphere, JPH::RVec3(2.0f, 0.0f, 0.0f), JPH::Quat::sIdentity(),
        JPH::EMotionType::Static, 0
    );
    auto& bodies = world.GetBodyInterface();
    auto* far = bodies.CreateBody(farSettings);
    auto* near = bodies.CreateBody(nearSettings);
    if (far == nullptr || near == nullptr) return 3;
    bodies.AddBody(far->GetID(), JPH::EActivation::DontActivate);
    bodies.AddBody(near->GetID(), JPH::EActivation::DontActivate);

    JPH::RayCastResult result;
    const JPH::RRayCast ray(JPH::RVec3::sZero(), JPH::Vec3(6.0f, 0.0f, 0.0f));
    if (!world.GetNarrowPhaseQuery().CastRay(ray, result)) return 4;
    std::cout.precision(9);
    std::cout << "near_fraction=" << result.mFraction << '\n'
              << "near_selected=" << (result.mBodyID == near->GetID() ? 1 : 0)
              << '\n';

    bodies.RemoveBody(near->GetID());
    bodies.RemoveBody(far->GetID());
    bodies.DestroyBody(near->GetID());
    bodies.DestroyBody(far->GetID());
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
