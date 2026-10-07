#include <array>
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
#include <Jolt/Physics/Constraints/PathConstraint.h>

#include <Jolt/Physics/Constraints/PathConstraintPathHermite.h>

namespace Physics3D {

// -----------------------------------------------------------------------------

int runPathCase(int caseId) {
    float length = caseId == 2 || caseId == 3 ? 1.0f : 20.0f;
    if (caseId == 12) length = 2;
    auto rotation = caseId == 10 ? JPH::Quat::sRotation(JPH::Vec3::sAxisZ(), 0.7f) : JPH::Quat::sIdentity();
    auto start = JPH::Vec3(caseId == 2 || caseId == 3 || caseId == 12 ? 0.0f : 2.0f, 0, 0);
    bool curved = caseId == 11 || caseId == 13;
    if (curved) start = JPH::Vec3(1, 0, 0);
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
    world.SetGravity(JPH::Vec3::sZero());
    JPH::RefConst<JPH::SphereShape> sphere = new JPH::SphereShape(0.25f);
    JPH::BodyCreationSettings settings(sphere, JPH::RVec3::sZero(), JPH::Quat::sIdentity(), JPH::EMotionType::Dynamic, 0);
    settings.mAllowSleeping = false;
    settings.mLinearDamping = settings.mAngularDamping = 0;
    settings.mOverrideMassProperties = JPH::EOverrideMassProperties::MassAndInertiaProvided;
    settings.mMassPropertiesOverride.mMass = 2;
    settings.mMassPropertiesOverride.mInertia = JPH::Mat44::sScale(JPH::Vec3::sReplicate(0.2f));
    auto& bodies = world.GetBodyInterface();
    settings.mRotation = rotation;
    settings.mMotionType = JPH::EMotionType::Static;
    auto* first = bodies.CreateBody(settings);
    settings.mMotionType = JPH::EMotionType::Dynamic;
    settings.mPosition = JPH::RVec3(rotation * start);
    auto* second = bodies.CreateBody(settings);
    if (!first || !second) return 3;
    bodies.AddBody(first->GetID(), JPH::EActivation::DontActivate);
    bodies.AddBody(second->GetID(), JPH::EActivation::Activate);
    JPH::Ref<JPH::PathConstraintPathHermite> path = new JPH::PathConstraintPathHermite;
    if (curved) {
        constexpr float h = 1.6568542495f;
        path->AddPoint(JPH::Vec3(1, 0, 0), JPH::Vec3(0, h, 0), JPH::Vec3::sAxisZ());
        path->AddPoint(JPH::Vec3(0, 1, 0), JPH::Vec3(-h, 0, 0), JPH::Vec3::sAxisZ());
        path->AddPoint(JPH::Vec3(-1, 0, 0), JPH::Vec3(0, -h, 0), JPH::Vec3::sAxisZ());
        path->AddPoint(JPH::Vec3(0, -1, 0), JPH::Vec3(h, 0, 0), JPH::Vec3::sAxisZ());
        path->SetIsLooping(true);
    } else {
        path->AddPoint(JPH::Vec3::sZero(), JPH::Vec3(length, 0, 0), JPH::Vec3::sAxisY());
        path->AddPoint(JPH::Vec3(length, 0, 0), JPH::Vec3(length, 0, 0), JPH::Vec3::sAxisY());
    }
    JPH::PathConstraintSettings coupling;
    coupling.mPath = path;
    coupling.mPathFraction = path->GetClosestPoint(start, 0);
    if (caseId == 4) coupling.mMaxFrictionForce = 6;
    if (caseId >= 5 && caseId <= 9) {
        constexpr std::array<JPH::EPathRotationConstraintType, 5> modes = {
            JPH::EPathRotationConstraintType::ConstrainAroundTangent, JPH::EPathRotationConstraintType::ConstrainAroundNormal,
            JPH::EPathRotationConstraintType::ConstrainAroundBinormal, JPH::EPathRotationConstraintType::ConstrainToPath,
            JPH::EPathRotationConstraintType::FullyConstrained};
        coupling.mRotationConstraintType = modes[caseId - 5];
    }
    if (caseId == 13) coupling.mRotationConstraintType = JPH::EPathRotationConstraintType::ConstrainToPath;
    coupling.mPositionMotorSettings.mMinForceLimit = -12;
    coupling.mPositionMotorSettings.mMaxForceLimit = 12;
    coupling.mPositionMotorSettings.mSpringSettings = JPH::SpringSettings(JPH::ESpringMode::StiffnessAndDamping, 40, 12);
    JPH::Ref<JPH::PathConstraint> joint = new JPH::PathConstraint(*first, *second, coupling);
    world.AddConstraint(joint.GetPtr());
    if (caseId == 1 || caseId == 10) { joint->SetPositionMotorState(JPH::EMotorState::Velocity); joint->SetTargetVelocity(1); }
    if (caseId == 2 || caseId == 3 || caseId == 12) {
        joint->SetPositionMotorState(caseId == 3 ? JPH::EMotorState::PositionAndVelocity : JPH::EMotorState::Position);
        joint->SetTargetPathFraction(0.5f / length);
        if (caseId == 3) joint->SetTargetVelocity(0.1f);
    }
    if (caseId == 0) bodies.SetLinearVelocity(second->GetID(), rotation * JPH::Vec3(1, 2, 3));
    if (caseId == 4) bodies.SetLinearVelocity(second->GetID(), JPH::Vec3::sAxisX());
    if (caseId >= 5 && caseId <= 9) bodies.SetAngularVelocity(second->GetID(), JPH::Vec3(1, 2, 3));
    if (curved) bodies.SetLinearVelocity(second->GetID(), JPH::Vec3::sAxisY());
    JPH::TempAllocatorImpl allocator(1024 * 1024);
    JPH::JobSystemSingleThreaded jobs(JPH::cMaxPhysicsJobs);
    for (int step = 1; step <= 120; ++step) {
        if (world.Update(1.0f / 60.0f, 1, &allocator, &jobs) != JPH::EPhysicsUpdateError::None) return 4;
        if (step == 1 || step % 15 == 0) {
            auto p = rotation.Conjugated() * JPH::Vec3(bodies.GetPosition(second->GetID()));
            auto v = rotation.Conjugated() * bodies.GetLinearVelocity(second->GetID());
            auto w = rotation.Conjugated() * bodies.GetAngularVelocity(second->GetID());
            auto q = rotation.Conjugated() * bodies.GetRotation(second->GetID());
            float angle = 2 * std::atan2(q.GetZ(), q.GetW());
            auto n = joint->GetTotalLambdaPosition();
            std::cout << "path " << caseId << ' ' << step << ' ' << p.GetX() << ' ' << p.GetY() << ' ' << p.GetZ()
                << ' ' << v.GetX() << ' ' << v.GetY() << ' ' << v.GetZ()
                << ' ' << w.GetX() << ' ' << w.GetY() << ' ' << w.GetZ()
                << ' ' << angle << ' ' << joint->GetTotalLambdaMotor() * 60
                << ' ' << n[0] * 60 << ' ' << n[1] * 60 << '\n';
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
    for (int caseId = 0; caseId < 14 && result == 0; ++caseId) result = Physics3D::runPathCase(caseId);
    JPH::UnregisterTypes();
    JPH::Factory::sInstance = nullptr;
    return result;
}
