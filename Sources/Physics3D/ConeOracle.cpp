#include <cmath>
#include <cstdlib>
#include <iostream>
#include <memory>
#include <Jolt/Jolt.h>
#include <Jolt/RegisterTypes.h>
#include <Jolt/Core/Factory.h>
#include <Jolt/Core/IssueReporting.h>
#include <Jolt/Core/JobSystemSingleThreaded.h>
#include <Jolt/Core/TempAllocator.h>
#include <Jolt/Physics/PhysicsSystem.h>
#include <Jolt/Physics/Body/BodyCreationSettings.h>
#include <Jolt/Physics/Collision/BroadPhase/BroadPhaseLayerInterfaceTable.h>
#include <Jolt/Physics/Collision/BroadPhase/ObjectVsBroadPhaseLayerFilterTable.h>
#include <Jolt/Physics/Collision/ObjectLayerPairFilterTable.h>
#include <Jolt/Physics/Collision/Shape/SphereShape.h>
#include <Jolt/Physics/Constraints/ConeConstraint.h>

namespace Physics3D {

// -----------------------------------------------------------------------------

int runConeCase(int caseId) {
    JPH::BroadPhaseLayerInterfaceTable broadPhase(1, 1);
    broadPhase.MapObjectToBroadPhaseLayer(0, JPH::BroadPhaseLayer(0));
    JPH::ObjectLayerPairFilterTable pairFilter(1);
    JPH::ObjectVsBroadPhaseLayerFilterTable phaseFilter(broadPhase, 1, pairFilter, 1);
    JPH::PhysicsSystem world;
    world.Init(16, 0, 16, 16, broadPhase, phaseFilter, pairFilter);
    auto physicsSettings = world.GetPhysicsSettings();
    physicsSettings.mNumVelocitySteps = 24;
    physicsSettings.mNumPositionSteps = 8;
    world.SetPhysicsSettings(physicsSettings);
    world.SetGravity(caseId == 6 ? JPH::Vec3(0, -9.81f, 0) : JPH::Vec3::sZero());
    JPH::RefConst<JPH::SphereShape> sphere = new JPH::SphereShape(0.25f);
    auto rotation = caseId == 7 ? JPH::Quat::sRotation(JPH::Vec3::sAxisY(), 0.7f) : JPH::Quat::sIdentity();
    auto firstType = caseId == 5 ? JPH::EMotionType::Dynamic : JPH::EMotionType::Static;
    JPH::BodyCreationSettings firstSettings(sphere, JPH::RVec3::sZero(), rotation, firstType, 0);
    firstSettings.mAllowSleeping = false;
    firstSettings.mLinearDamping = firstSettings.mAngularDamping = 0;
    firstSettings.mOverrideMassProperties = JPH::EOverrideMassProperties::MassAndInertiaProvided;
    firstSettings.mMassPropertiesOverride.mMass = 2;
    firstSettings.mMassPropertiesOverride.mInertia = JPH::Mat44::sScale(JPH::Vec3::sReplicate(0.2f));
    const float mass = caseId == 5 ? 8.0f : 2.0f;
    auto position = caseId == 6 ? JPH::RVec3(0, -1, 0) : JPH::RVec3::sZero();
    auto anchor = caseId == 6 ? JPH::Vec3::sAxisY() : JPH::Vec3::sZero();
    JPH::BodyCreationSettings secondSettings(sphere, position, rotation, JPH::EMotionType::Dynamic, 0);
    secondSettings.mAllowSleeping = false;
    secondSettings.mLinearDamping = secondSettings.mAngularDamping = 0;
    secondSettings.mOverrideMassProperties = JPH::EOverrideMassProperties::MassAndInertiaProvided;
    secondSettings.mMassPropertiesOverride.mMass = mass;
    secondSettings.mMassPropertiesOverride.mInertia = JPH::Mat44::sScale(JPH::Vec3::sReplicate(mass * 0.1f));
    auto& bodies = world.GetBodyInterface();
    auto* first = bodies.CreateBody(firstSettings);
    auto* second = bodies.CreateBody(secondSettings);
    if (!first || !second) return 3;
    bodies.AddBody(first->GetID(), caseId == 5 ? JPH::EActivation::Activate : JPH::EActivation::DontActivate);
    bodies.AddBody(second->GetID(), JPH::EActivation::Activate);
    JPH::ConeConstraintSettings settings;
    settings.mSpace = JPH::EConstraintSpace::LocalToBodyCOM;
    settings.mPoint1 = JPH::RVec3::sZero();
    settings.mPoint2 = JPH::RVec3(anchor);
    settings.mTwistAxis1 = settings.mTwistAxis2 = JPH::Vec3::sAxisZ();
    settings.mHalfConeAngle = 0.4f;
    JPH::Ref<JPH::ConeConstraint> joint = new JPH::ConeConstraint(*first, *second, settings);
    world.AddConstraint(joint.GetPtr());
    auto speed = JPH::Vec3(2, 0, 0);
    if (caseId == 0) speed = JPH::Vec3(0, 0, 0.5f);
    if (caseId == 2) speed = JPH::Vec3(-2, 0, 0);
    if (caseId == 3 || caseId == 6) speed = JPH::Vec3::sZero();
    bodies.SetAngularVelocity(second->GetID(), rotation * speed);
    JPH::TempAllocatorImpl allocator(1024 * 1024);
    JPH::JobSystemSingleThreaded jobs(JPH::cMaxPhysicsJobs);
    constexpr float delta = 1.0f / 60.0f;
    for (int step = 1; step <= 360; ++step) {
        if (caseId == 3) bodies.AddTorque(second->GetID(), JPH::Vec3(0.2f, 0, 0));
        if (caseId == 4 && step == 181) { joint->SetHalfConeAngle(0.2f); joint->ResetWarmStart(); }
        if (world.Update(delta, 1, &allocator, &jobs) != JPH::EPhysicsUpdateError::None) return 4;
        if (step % 15 == 0) {
            const auto firstRotation = bodies.GetRotation(first->GetID());
            const auto secondRotation = bodies.GetRotation(second->GetID());
            const auto a = firstRotation * JPH::Vec3::sAxisZ();
            const auto b = secondRotation * JPH::Vec3::sAxisZ();
            const float angle = std::atan2(a.Cross(b).Length(), a.Dot(b));
            const auto point = bodies.GetPosition(second->GetID()) + secondRotation * anchor;
            const auto angular = bodies.GetAngularVelocity(second->GetID());
            const auto firstAngular = bodies.GetAngularVelocity(first->GetID());
            const auto force = joint->GetTotalLambdaPosition() / delta;
            const auto axis = b.Cross(a).NormalizedOr(JPH::Vec3::sAxisX());
            const auto torque = axis * (joint->GetTotalLambdaRotation() / delta);
            std::cout << "cone " << caseId << ' ' << step << ' ' << angle
                << ' ' << angular.GetX() << ' ' << angular.GetY() << ' ' << angular.GetZ()
                << ' ' << firstAngular.GetX() << ' ' << (point - bodies.GetPosition(first->GetID())).Length()
                << ' ' << force.GetX() << ' ' << force.GetY() << ' ' << force.GetZ()
                << ' ' << torque.GetX() << ' ' << torque.GetY() << ' ' << torque.GetZ() << '\n';
        }
    }
    world.RemoveConstraint(joint.GetPtr());
    bodies.RemoveBody(first->GetID()); bodies.RemoveBody(second->GetID());
    bodies.DestroyBody(first->GetID()); bodies.DestroyBody(second->GetID());
    return 0;
}

// -----------------------------------------------------------------------------

} // namespace Physics3D

int main() {
#ifdef JPH_ENABLE_ASSERTS
    JPH::AssertFailed = [](const char* expression, const char* message, const char* file, JPH::uint line) {
        std::cerr << "Jolt assertion: " << expression << " at " << file << ':' << line
            << " message=" << (message ? message : "") << '\n';
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
    for (int caseId = 0; caseId < 8 && result == 0; ++caseId) result = Physics3D::runConeCase(caseId);
    JPH::UnregisterTypes();
    JPH::Factory::sInstance = nullptr;
    return result;
}
