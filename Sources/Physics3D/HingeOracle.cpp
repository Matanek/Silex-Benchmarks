#include <Jolt/Jolt.h>
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
#include <Jolt/Physics/Constraints/HingeConstraint.h>
#include <cmath>
#include <iostream>

namespace Physics3D {

// -----------------------------------------------------------------------------

int runCase(int caseId) {
    JPH::BroadPhaseLayerInterfaceTable broadPhase(1, 1);
    broadPhase.MapObjectToBroadPhaseLayer(0, JPH::BroadPhaseLayer(0));
    JPH::ObjectLayerPairFilterTable pairFilter(1);
    JPH::ObjectVsBroadPhaseLayerFilterTable phaseFilter(broadPhase, 1, pairFilter, 1);
    JPH::PhysicsSystem world;
    world.Init(16, 0, 16, 16, broadPhase, phaseFilter, pairFilter);
    world.SetGravity(caseId == 1 || caseId == 3 ? JPH::Vec3(0, -9.81f, 0) : JPH::Vec3::sZero());
    JPH::RefConst<JPH::SphereShape> sphere = new JPH::SphereShape(0.5f);
    auto position = JPH::RVec3::sZero();
    auto rotation = JPH::Quat::sIdentity();
    auto localAnchor = JPH::Vec3::sZero();
    auto speed = JPH::Vec3(3, -2, 1);
    if (caseId == 1) {
        localAnchor = JPH::Vec3(0, 1, 0);
        position = JPH::RVec3(0, -1, 0);
        speed = JPH::Vec3::sZero();
    }
    if (caseId == 2) speed = JPH::Vec3(0, 0, 2);
    if (caseId == 3) {
        localAnchor = JPH::Vec3(0, 2, 0);
        rotation = JPH::Quat::sRotation(JPH::Vec3::sAxisZ(), 0.6f);
        position = JPH::RVec3(rotation * -localAnchor);
        speed = JPH::Vec3::sZero();
    }
    JPH::BodyCreationSettings fixedSettings(sphere, JPH::RVec3::sZero(), JPH::Quat::sIdentity(), JPH::EMotionType::Static, 0);
    JPH::BodyCreationSettings dynamicSettings(sphere, position, rotation, JPH::EMotionType::Dynamic, 0);
    dynamicSettings.mAllowSleeping = false;
    dynamicSettings.mLinearDamping = 0;
    dynamicSettings.mAngularDamping = 0;
    dynamicSettings.mAngularVelocity = speed;
    dynamicSettings.mOverrideMassProperties = JPH::EOverrideMassProperties::CalculateInertia;
    dynamicSettings.mMassPropertiesOverride.mMass = 1;
    auto& bodies = world.GetBodyInterface();
    auto* first = bodies.CreateBody(fixedSettings);
    auto* second = bodies.CreateBody(dynamicSettings);
    if (!first || !second) return 3;
    bodies.AddBody(first->GetID(), JPH::EActivation::DontActivate);
    bodies.AddBody(second->GetID(), JPH::EActivation::Activate);
    JPH::HingeConstraintSettings settings;
    settings.mSpace = JPH::EConstraintSpace::LocalToBodyCOM;
    settings.mPoint1 = JPH::RVec3::sZero();
    settings.mPoint2 = JPH::RVec3(localAnchor);
    settings.mHingeAxis1 = settings.mHingeAxis2 = JPH::Vec3::sAxisZ();
    settings.mNormalAxis1 = settings.mNormalAxis2 = JPH::Vec3::sAxisX();
    if (caseId == 2) { settings.mLimitsMin = -0.3f; settings.mLimitsMax = 0.4f; }
    JPH::Ref<JPH::HingeConstraint> joint = new JPH::HingeConstraint(*first, *second, settings);
    world.AddConstraint(joint.GetPtr());
    JPH::TempAllocatorImpl allocator(1024 * 1024);
    JPH::JobSystemSingleThreaded jobs(JPH::cMaxPhysicsJobs);
    constexpr auto delta = 1.0f / 60.0f;
    for (auto step = 1; step <= 120; ++step) {
        if (caseId == 2 && step == 61) {
            joint->SetLimits(-0.2f, 0.2f);
            bodies.SetAngularVelocity(second->GetID(), JPH::Vec3(0, 0, -2));
        }
        if (world.Update(delta, 1, &allocator, &jobs) != JPH::EPhysicsUpdateError::None) return 4;
        if (step % 15 == 0) {
            const auto point = bodies.GetPosition(second->GetID());
            const auto orientation = bodies.GetRotation(second->GetID());
            const auto axis = orientation * JPH::Vec3::sAxisZ();
            const auto axisError = std::atan2(JPH::Vec3::sAxisZ().Cross(axis).Length(), axis.GetZ());
            std::cout << "hinge " << caseId << ' ' << step << ' ' << point.GetX() << ' ' << point.GetY()
                      << ' ' << joint->GetCurrentAngle() << ' ' << bodies.GetAngularVelocity(second->GetID()).GetZ()
                      << ' ' << (point + orientation * localAnchor).Length() << ' ' << axisError
                      << ' ' << joint->GetTotalLambdaPosition().GetY() / delta << '\n';
        }
    }
    world.RemoveConstraint(joint.GetPtr());
    bodies.RemoveBody(first->GetID());
    bodies.RemoveBody(second->GetID());
    bodies.DestroyBody(first->GetID());
    bodies.DestroyBody(second->GetID());
    return 0;
}

// -----------------------------------------------------------------------------

} // namespace Physics3D

int main() {
    JPH::RegisterDefaultAllocator();
    JPH::Factory::sInstance = new JPH::Factory();
    JPH::RegisterTypes();
    std::cout.precision(9);
    auto result = 0;
    for (auto caseId = 0; caseId < 4 && result == 0; ++caseId) result = Physics3D::runCase(caseId);
    JPH::UnregisterTypes();
    delete JPH::Factory::sInstance;
    JPH::Factory::sInstance = nullptr;
    return result;
}
