#include <cmath>
#include <iostream>
#include <memory>
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
#include <Jolt/Physics/Constraints/FixedConstraint.h>

namespace Physics3D {

// -----------------------------------------------------------------------------

int runFixedCase(int caseId) {
    JPH::BroadPhaseLayerInterfaceTable broadPhase(1, 1);
    broadPhase.MapObjectToBroadPhaseLayer(0, JPH::BroadPhaseLayer(0));
    JPH::ObjectLayerPairFilterTable pairFilter(1);
    JPH::ObjectVsBroadPhaseLayerFilterTable phaseFilter(broadPhase, 1, pairFilter, 1);
    JPH::PhysicsSystem world;
    world.Init(16, 0, 16, 16, broadPhase, phaseFilter, pairFilter);
    auto options = world.GetPhysicsSettings();
    options.mNumVelocitySteps = 12;
    options.mNumPositionSteps = 4;
    world.SetPhysicsSettings(options);
    world.SetGravity(caseId == 0 || caseId == 3 || caseId == 4 ? JPH::Vec3(0, -9.81f, 0) : JPH::Vec3::sZero());
    JPH::RefConst<JPH::SphereShape> sphere = new JPH::SphereShape(0.5f);
    auto& bodies = world.GetBodyInterface();
    auto makeBody = [&](JPH::Vec3 position, JPH::Quat rotation, JPH::EMotionType type, float mass) {
        JPH::BodyCreationSettings settings(sphere, JPH::RVec3(position), rotation, type, 0);
        settings.mAllowSleeping = false;
        settings.mLinearDamping = settings.mAngularDamping = 0;
        settings.mOverrideMassProperties = JPH::EOverrideMassProperties::MassAndInertiaProvided;
        settings.mMassPropertiesOverride.mMass = mass;
        settings.mMassPropertiesOverride.mInertia = JPH::Mat44::sScale(JPH::Vec3::sReplicate(mass * 0.1f));
        return bodies.CreateAndAddBody(settings, type == JPH::EMotionType::Static ? JPH::EActivation::DontActivate : JPH::EActivation::Activate);
    };
    const auto firstType = caseId == 2 ? JPH::EMotionType::Dynamic : caseId == 5 ? JPH::EMotionType::Kinematic : JPH::EMotionType::Static;
    const auto firstId = makeBody(JPH::Vec3::sZero(), JPH::Quat::sIdentity(), firstType, 2);
    auto position = caseId == 2 ? JPH::Vec3::sZero() : JPH::Vec3(caseId == 4 ? 1 : 2, 0, 0);
    const auto rotation = caseId == 1 ? JPH::Quat::sRotation(JPH::Vec3::sAxisY(), 3.13f) : JPH::Quat::sIdentity();
    const auto secondId = makeBody(position, rotation, JPH::EMotionType::Dynamic, caseId == 2 ? 8 : 2);
    if (firstId.IsInvalid() || secondId.IsInvalid()) return 3;
    auto frame1 = JPH::Quat::sIdentity();
    auto frame2 = JPH::Quat::sIdentity();
    auto anchor1 = JPH::Vec3::sZero();
    auto anchor2 = -position;
    if (caseId == 1) {
        anchor1 = JPH::Vec3(1, 2, 0); anchor2 = JPH::Vec3(0, 1, 0);
        frame1 = JPH::Quat::sRotation(JPH::Vec3::sAxisX(), 0.4f);
        frame2 = JPH::Quat::sRotation(JPH::Vec3::sAxisZ(), -0.3f);
    }
    auto makeJoint = [&](JPH::BodyID a, JPH::BodyID b, JPH::Vec3 p1, JPH::Vec3 p2, JPH::Quat q1, JPH::Quat q2) {
        JPH::FixedConstraintSettings settings;
        settings.mSpace = JPH::EConstraintSpace::LocalToBodyCOM;
        settings.mPoint1 = JPH::RVec3(p1); settings.mPoint2 = JPH::RVec3(p2);
        settings.mAxisX1 = q1 * JPH::Vec3::sAxisX(); settings.mAxisY1 = q1 * JPH::Vec3::sAxisY();
        settings.mAxisX2 = q2 * JPH::Vec3::sAxisX(); settings.mAxisY2 = q2 * JPH::Vec3::sAxisY();
        JPH::Ref<JPH::FixedConstraint> result = static_cast<JPH::FixedConstraint*>(bodies.CreateConstraint(&settings, a, b));
        world.AddConstraint(result.GetPtr());
        return result;
    };
    auto joint = makeJoint(firstId, secondId, anchor1, anchor2, frame1, frame2);
    JPH::Ref<JPH::FixedConstraint> lower;
    JPH::BodyID thirdId;
    if (caseId == 4) {
        thirdId = makeBody(JPH::Vec3(2, 0, 0), JPH::Quat::sIdentity(), JPH::EMotionType::Dynamic, 8);
        if (thirdId.IsInvalid()) return 3;
        lower = makeJoint(secondId, thirdId, JPH::Vec3::sZero(), JPH::Vec3(-1, 0, 0), JPH::Quat::sIdentity(), JPH::Quat::sIdentity());
    }
    if (caseId == 2) {
        bodies.SetLinearVelocity(firstId, JPH::Vec3::sAxisX()); bodies.SetAngularVelocity(firstId, JPH::Vec3::sAxisZ());
    }
    if (caseId == 5) bodies.MoveKinematic(firstId, JPH::RVec3(0, 4, 0), JPH::Quat::sRotation(JPH::Vec3::sAxisZ(), 0.8f), 4);
    JPH::TempAllocatorImpl allocator(1024 * 1024);
    JPH::JobSystemSingleThreaded jobs(JPH::cMaxPhysicsJobs);
    constexpr float delta = 1.0f / 60.0f;
    for (int step = 1; step <= 1620; ++step) {
        if (caseId == 3 && step == 361) joint->SetEnabled(false);
        if (caseId == 3 && step == 391) joint->SetEnabled(true);
        if (world.Update(delta, 1, &allocator, &jobs) != JPH::EPhysicsUpdateError::None) return 4;
        const bool sampled = (caseId == 0 && step >= 90 && step <= 300) ||
            (caseId == 1 && step >= 150 && step <= 360) || (caseId == 2 && step <= 240) ||
            (caseId == 3 && (step == 90 || step == 120 || step == 390 || (step >= 1500 && step <= 1620))) ||
            (caseId == 4 && step >= 900 && step <= 1110) || (caseId == 5 && step <= 240);
        if (step % 30 == 0 && sampled) {
            const auto point = bodies.GetPosition(secondId);
            const auto orientation = bodies.GetRotation(secondId);
            const auto axis = orientation * JPH::Vec3::sAxisX();
            const auto difference = ((orientation * frame2) * (bodies.GetRotation(firstId) * frame1).Conjugated()).Normalized();
            const float angle = 2 * std::atan2(JPH::Vec3(difference.GetX(), difference.GetY(), difference.GetZ()).Length(), std::abs(difference.GetW()));
            const float error = (point + orientation * anchor2 - bodies.GetPosition(firstId) - bodies.GetRotation(firstId) * anchor1).Length();
            std::cout << "fixed " << caseId << ' ' << step << ' ' << point.GetX() << ' ' << point.GetY() << ' ' << point.GetZ()
                << ' ' << axis.GetX() << ' ' << axis.GetY() << ' ' << axis.GetZ() << ' ' << error << ' ' << angle
                << ' ' << (joint->GetEnabled() ? joint->GetTotalLambdaPosition().GetY() / delta : 0)
                << ' ' << (joint->GetEnabled() ? joint->GetTotalLambdaRotation().GetZ() / delta : 0)
                << ' ' << bodies.GetLinearVelocity(secondId).GetX() << ' ' << bodies.GetAngularVelocity(secondId).GetZ()
                << ' ' << bodies.GetLinearVelocity(firstId).GetX() << ' ' << bodies.GetAngularVelocity(firstId).GetZ() << '\n';
        }
    }
    if (lower) world.RemoveConstraint(lower.GetPtr());
    world.RemoveConstraint(joint.GetPtr());
    for (const auto id : {firstId, secondId, thirdId}) {
        if (!id.IsInvalid()) { bodies.RemoveBody(id); bodies.DestroyBody(id); }
    }
    return 0;
}

// -----------------------------------------------------------------------------

} // namespace Physics3D

int main() {
    JPH::RegisterDefaultAllocator();
    auto factory = std::make_unique<JPH::Factory>();
    JPH::Factory::sInstance = factory.get();
    JPH::RegisterTypes();
    std::cout.precision(9);
    int result = 0;
    for (int caseId = 0; caseId < 6 && result == 0; ++caseId) result = Physics3D::runFixedCase(caseId);
    JPH::UnregisterTypes();
    JPH::Factory::sInstance = nullptr;
    return result;
}
