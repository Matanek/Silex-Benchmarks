#include <Jolt/Jolt.h>
#include <Jolt/ConfigurationString.h>
#include <Jolt/RegisterTypes.h>
#include <Jolt/Core/Factory.h>
#include <Jolt/Core/JobSystemSingleThreaded.h>
#include <Jolt/Core/TempAllocator.h>
#include <Jolt/Physics/PhysicsSystem.h>
#include <Jolt/Physics/Body/BodyCreationSettings.h>
#include <Jolt/Physics/Collision/ContactListener.h>
#include <Jolt/Physics/Collision/BroadPhase/BroadPhaseLayerInterfaceTable.h>
#include <Jolt/Physics/Collision/BroadPhase/ObjectVsBroadPhaseLayerFilterTable.h>
#include <Jolt/Physics/Collision/ObjectLayerPairFilterTable.h>
#include <Jolt/Physics/Collision/Shape/SphereShape.h>
#include <iostream>
#include <string_view>

namespace Physics3D {

class Events final : public JPH::ContactListener {
public:
    int added = 0;
    int persisted = 0;
    int removed = 0;

    void OnContactAdded(const JPH::Body&, const JPH::Body&,
                        const JPH::ContactManifold&,
                        JPH::ContactSettings&) override { ++added; }
    void OnContactPersisted(const JPH::Body&, const JPH::Body&,
                            const JPH::ContactManifold&,
                            JPH::ContactSettings&) override { ++persisted; }
    void OnContactRemoved(const JPH::SubShapeIDPair&) override { ++removed; }

    void clear() { added = persisted = removed = 0; }
    void print(const char* phase) const {
        std::cout << phase << "_added=" << added << '\n'
                  << phase << "_persisted=" << persisted << '\n'
                  << phase << "_removed=" << removed << '\n';
    }
};

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
    Events events;
    world.SetContactListener(&events);
    JPH::RefConst<JPH::SphereShape> sphere = new JPH::SphereShape(0.5f);
    JPH::BodyCreationSettings fixedSettings(
        sphere, JPH::RVec3::sZero(), JPH::Quat::sIdentity(),
        JPH::EMotionType::Static, 0
    );
    JPH::BodyCreationSettings movingSettings(
        sphere, JPH::RVec3(0.9f, 0.0f, 0.0f), JPH::Quat::sIdentity(),
        JPH::EMotionType::Dynamic, 0
    );
    movingSettings.mAllowSleeping = false;
    auto& bodies = world.GetBodyInterface();
    const auto fixed = bodies.CreateAndAddBody(fixedSettings, JPH::EActivation::DontActivate);
    const auto moving = bodies.CreateAndAddBody(movingSettings, JPH::EActivation::Activate);
    if (fixed.IsInvalid() || moving.IsInvalid()) return 3;
    JPH::TempAllocatorImpl allocator(1024 * 1024);
    JPH::JobSystemSingleThreaded jobs(JPH::cMaxPhysicsJobs);
    const auto step = [&] {
        return world.Update(1.0f / 60.0f, 1, &allocator, &jobs) ==
            JPH::EPhysicsUpdateError::None;
    };
    if (!step()) return 4;
    events.print("entry");
    events.clear();
    if (!step()) return 4;
    events.print("stay");
    events.clear();
    bodies.RemoveBody(fixed);
    bodies.DestroyBody(fixed);
    if (!step()) return 4;
    events.print("destroy");
    bodies.RemoveBody(moving);
    bodies.DestroyBody(moving);
    world.SetContactListener(nullptr);
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
