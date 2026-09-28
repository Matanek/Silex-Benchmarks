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
#include <Jolt/Physics/Constraints/PointConstraint.h>
#include <cmath>
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
    world.SetGravity(JPH::Vec3(0.0f, -9.81f, 0.0f));
    JPH::RefConst<JPH::SphereShape> sphere = new JPH::SphereShape(0.5f);
    JPH::BodyCreationSettings anchorSettings(
        sphere, JPH::RVec3(0.0f, 2.0f, 0.0f), JPH::Quat::sIdentity(),
        JPH::EMotionType::Static, 0
    );
    JPH::BodyCreationSettings weightSettings(
        sphere, JPH::RVec3(0.0f, 1.0f, 0.0f), JPH::Quat::sIdentity(),
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

    JPH::PointConstraintSettings pointSettings;
    pointSettings.mSpace = JPH::EConstraintSpace::LocalToBodyCOM;
    pointSettings.mPoint1 = JPH::RVec3(0.0f, 0.0f, 0.0f);
    pointSettings.mPoint2 = JPH::RVec3(0.0f, 1.0f, 0.0f);
    JPH::Ref<JPH::PointConstraint> constraint =
        new JPH::PointConstraint(*anchor, *weight, pointSettings);
    world.AddConstraint(constraint.GetPtr());

    JPH::BodyCreationSettings pivotSettings(
        sphere, JPH::RVec3(10.0f, 3.0f, 0.0f), JPH::Quat::sIdentity(),
        JPH::EMotionType::Static, 0
    );
    JPH::BodyCreationSettings pendulumSettings(
        sphere, JPH::RVec3(11.0f, 1.0f, 0.0f), JPH::Quat::sIdentity(),
        JPH::EMotionType::Dynamic, 0
    );
    pendulumSettings.mLinearDamping = 0.0f;
    pendulumSettings.mAngularDamping = 0.0f;
    pendulumSettings.mAllowSleeping = false;
    auto* pivot = bodies.CreateBody(pivotSettings);
    auto* pendulum = bodies.CreateBody(pendulumSettings);
    if (pivot == nullptr || pendulum == nullptr) return 3;
    bodies.AddBody(pivot->GetID(), JPH::EActivation::DontActivate);
    bodies.AddBody(pendulum->GetID(), JPH::EActivation::Activate);
    JPH::PointConstraintSettings pendulumPointSettings;
    pendulumPointSettings.mSpace = JPH::EConstraintSpace::LocalToBodyCOM;
    pendulumPointSettings.mPoint1 = JPH::RVec3(0.0f, 0.0f, 0.0f);
    pendulumPointSettings.mPoint2 = JPH::RVec3(-1.0f, 2.0f, 0.0f);
    JPH::Ref<JPH::PointConstraint> pendulumConstraint =
        new JPH::PointConstraint(*pivot, *pendulum, pendulumPointSettings);
    world.AddConstraint(pendulumConstraint.GetPtr());

    JPH::TempAllocatorImpl allocator(1024 * 1024);
    JPH::JobSystemSingleThreaded jobs(JPH::cMaxPhysicsJobs);
    constexpr auto delta = 1.0f / 60.0f;
    for (auto step = 0; step < 120; ++step) {
        if (world.Update(delta, 1, &allocator, &jobs) != JPH::EPhysicsUpdateError::None) {
            return 4;
        }
    }
    const auto height = bodies.GetPosition(weight->GetID()).GetY();
    const auto mass = 1.0f / weight->GetMotionProperties()->GetInverseMass();
    const auto pendulumPosition = bodies.GetPosition(pendulum->GetID());
    const auto pendulumPoint = pendulumPosition +
        bodies.GetRotation(pendulum->GetID()) * JPH::Vec3(-1.0f, 2.0f, 0.0f);
    std::cout.precision(9);
    std::cout << "anchor_error=" << std::abs(2.0f - (height + 1.0f)) << '\n'
              << "height=" << height << '\n'
              << "reaction_weight_ratio=" <<
                  std::abs(constraint->GetTotalLambdaPosition().GetY()) /
                      (delta * mass * 9.81f)
              << '\n'
              << "pendulum_error=" << (pendulumPoint - JPH::RVec3(10.0f, 3.0f, 0.0f)).Length()
              << '\n'
              << "pendulum_x=" << pendulumPosition.GetX() - 10.0f
              << '\n';

    world.RemoveConstraint(pendulumConstraint.GetPtr());
    world.RemoveConstraint(constraint.GetPtr());
    bodies.RemoveBody(pendulum->GetID());
    bodies.RemoveBody(pivot->GetID());
    bodies.RemoveBody(weight->GetID());
    bodies.RemoveBody(anchor->GetID());
    bodies.DestroyBody(pendulum->GetID());
    bodies.DestroyBody(pivot->GetID());
    bodies.DestroyBody(weight->GetID());
    bodies.DestroyBody(anchor->GetID());
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
