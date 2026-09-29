#include <iostream>
#include <string_view>
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
#include <Jolt/Physics/Constraints/DistanceConstraint.h>

namespace Physics3D {

// -----------------------------------------------------------------------------

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
    JPH::BodyCreationSettings anchorSettings(
        sphere, JPH::RVec3::sZero(), JPH::Quat::sIdentity(),
        JPH::EMotionType::Static, 0
    );
    JPH::BodyCreationSettings weightSettings(
        sphere, JPH::RVec3(3.0f, 0.0f, 0.0f), JPH::Quat::sIdentity(),
        JPH::EMotionType::Dynamic, 0
    );
    weightSettings.mLinearDamping = 0.0f;
    weightSettings.mAngularDamping = 0.0f;
    weightSettings.mAllowSleeping = false;
    auto& bodies = world.GetBodyInterface();
    auto* anchor = bodies.CreateBody(anchorSettings);
    auto* weight = bodies.CreateBody(weightSettings);
    if (anchor == nullptr || weight == nullptr) return 3;
    bodies.AddBody(anchor->GetID(), JPH::EActivation::DontActivate);
    bodies.AddBody(weight->GetID(), JPH::EActivation::Activate);

    JPH::DistanceConstraintSettings settings;
    settings.mSpace = JPH::EConstraintSpace::LocalToBodyCOM;
    settings.mMinDistance = 2.0f;
    settings.mMaxDistance = 2.0f;
    settings.mLimitsSpringSettings.mFrequency = 2.0f;
    settings.mLimitsSpringSettings.mDamping = 0.1f;
    JPH::Ref<JPH::DistanceConstraint> joint =
        new JPH::DistanceConstraint(*anchor, *weight, settings);
    world.AddConstraint(joint.GetPtr());

    JPH::TempAllocatorImpl allocator(1024 * 1024);
    JPH::JobSystemSingleThreaded jobs(JPH::cMaxPhysicsJobs);
    constexpr float delta = 1.0f / 60.0f;
    std::cout.precision(9);
    for (int step = 1; step <= 120; ++step) {
        if (world.Update(delta, 1, &allocator, &jobs) != JPH::EPhysicsUpdateError::None) {
            return 4;
        }
        if (step == 12 || step == 30 || step == 60 || step == 120) {
            std::cout << "length_" << step << '='
                      << bodies.GetPosition(weight->GetID()).GetX() << '\n';
        }
    }

    world.RemoveConstraint(joint.GetPtr());
    bodies.RemoveBody(weight->GetID());
    bodies.RemoveBody(anchor->GetID());
    bodies.DestroyBody(weight->GetID());
    bodies.DestroyBody(anchor->GetID());
    JPH::UnregisterTypes();
    delete JPH::Factory::sInstance;
    JPH::Factory::sInstance = nullptr;
    return 0;
}

// -----------------------------------------------------------------------------

} // namespace Physics3D

int main(int count, char** values) {
    if (count == 2 && std::string_view(values[1]) == "--configuration") {
        std::cout << JPH::GetConfigurationString() << '\n';
        return 0;
    }
    if (count != 1) return 2;
    return Physics3D::run();
}
