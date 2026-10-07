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
#include <Jolt/Physics/Constraints/SwingTwistConstraint.h>

namespace Physics3D {

// -----------------------------------------------------------------------------

int runSwingTwistCase(int caseId) {
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
    world.SetGravity(caseId == 8 ? JPH::Vec3(0, -9.81f, 0) : JPH::Vec3::sZero());
    JPH::RefConst<JPH::SphereShape> sphere = new JPH::SphereShape(0.25f);
    auto rotation = caseId == 9 ? JPH::Quat::sRotation(JPH::Vec3::sAxisY(), 0.7f) : JPH::Quat::sIdentity();
    auto firstType = caseId == 7 ? JPH::EMotionType::Dynamic : JPH::EMotionType::Static;
    JPH::BodyCreationSettings firstSettings(sphere, JPH::RVec3::sZero(), rotation, firstType, 0);
    firstSettings.mAllowSleeping = false;
    firstSettings.mLinearDamping = firstSettings.mAngularDamping = 0;
    firstSettings.mOverrideMassProperties = JPH::EOverrideMassProperties::MassAndInertiaProvided;
    firstSettings.mMassPropertiesOverride.mMass = 2;
    firstSettings.mMassPropertiesOverride.mInertia = JPH::Mat44::sScale(JPH::Vec3::sReplicate(0.2f));
    const float mass = caseId == 7 ? 8.0f : 2.0f;
    auto position = caseId == 8 ? JPH::RVec3(0, -1, 0) : JPH::RVec3::sZero();
    auto anchor = caseId == 8 ? JPH::Vec3::sAxisY() : JPH::Vec3::sZero();
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
    bodies.AddBody(first->GetID(), caseId == 7 ? JPH::EActivation::Activate : JPH::EActivation::DontActivate);
    bodies.AddBody(second->GetID(), JPH::EActivation::Activate);
    JPH::SwingTwistConstraintSettings settings;
    settings.mSpace = JPH::EConstraintSpace::LocalToBodyCOM;
    // Jolt builds frame Y as planeAxis cross twistAxis: Z gives the identity frame.
    settings.mPlaneAxis1 = settings.mPlaneAxis2 = JPH::Vec3::sAxisZ();
    settings.mPosition1 = JPH::RVec3::sZero();
    settings.mPosition2 = JPH::RVec3(anchor);
    settings.mPlaneHalfConeAngle = 0.3f;
    settings.mNormalHalfConeAngle = 0.6f;
    settings.mTwistMinAngle = -0.4f;
    settings.mTwistMaxAngle = 0.5f;
    if (caseId == 0 || caseId == 4 || caseId == 5 || caseId == 6 || caseId == 8) {
        settings.mTwistMinAngle = -JPH::JPH_PI;
        settings.mTwistMaxAngle = JPH::JPH_PI;
    }
    if (caseId == 7) {
        settings.mTwistMinAngle = settings.mTwistMaxAngle = 0;
        settings.mPlaneHalfConeAngle = settings.mNormalHalfConeAngle = 0;
    }
    if (caseId == 6) settings.mMaxFrictionTorque = 0.2f;
    if (caseId == 10) settings.mSwingType = JPH::ESwingType::Pyramid;
    auto configureMotor = [](JPH::MotorSettings& motor) {
        motor.mMinTorqueLimit = -10;
        motor.mMaxTorqueLimit = 10;
        motor.mSpringSettings = JPH::SpringSettings(JPH::ESpringMode::StiffnessAndDamping, 2, 0.8f);
    };
    configureMotor(settings.mTwistMotorSettings);
    configureMotor(settings.mSwingMotorSettings);
    JPH::Ref<JPH::SwingTwistConstraint> joint = new JPH::SwingTwistConstraint(*first, *second, settings);
    world.AddConstraint(joint.GetPtr());
    auto speed = JPH::Vec3::sZero();
    if (caseId == 0) speed = JPH::Vec3(0.5f, 0, 0);
    if (caseId == 1) speed = JPH::Vec3(-2, 0, 0);
    if (caseId == 2 || caseId == 9 || caseId == 10) speed = JPH::Vec3(0, 2, 0);
    if (caseId == 3) speed = JPH::Vec3(0, 0, -2);
    if (caseId == 6 || caseId == 7) speed = JPH::Vec3(1, 0, 0);
    if (caseId == 11) speed = JPH::Vec3(1.7f, 0, 0);
    if (caseId == 4) {
        joint->SetTwistMotorState(JPH::EMotorState::PositionAndVelocity);
        joint->SetTargetOrientationCS(JPH::Quat::sRotation(JPH::Vec3::sAxisX(), 0.25f));
        joint->SetTargetAngularVelocityCS(JPH::Vec3(0.05f, 0, 0));
    }
    if (caseId == 5) {
        joint->SetSwingMotorState(JPH::EMotorState::PositionAndVelocity);
        joint->SetTargetOrientationCS(JPH::Quat::sRotation(JPH::Vec3::sAxisY(), 0.2f));
        joint->SetTargetAngularVelocityCS(JPH::Vec3(0, 0.05f, 0));
    }
    bodies.SetAngularVelocity(second->GetID(), rotation * speed);
    JPH::TempAllocatorImpl allocator(1024 * 1024);
    JPH::JobSystemSingleThreaded jobs(JPH::cMaxPhysicsJobs);
    constexpr float delta = 1.0f / 60.0f;
    for (int step = 1; step <= 360; ++step) {
        if (caseId == 11 && step == 181) { joint->SetTwistMaxAngle(0.2f); joint->ResetWarmStart(); }
        if (world.Update(delta, 1, &allocator, &jobs) != JPH::EPhysicsUpdateError::None) return 4;
        if (step % 15 == 0) {
            const auto q = joint->GetRotationInConstraintSpace();
            JPH::Quat swing, twist;
            q.GetSwingTwist(swing, twist);
            if (swing.GetW() < 0) swing = -swing;
            if (twist.GetW() < 0) twist = -twist;
            const float twistAngle = 2 * std::atan2(twist.GetX(), twist.GetW());
            const float swingY = 2 * std::atan2(swing.GetY(), swing.GetW());
            const float swingZ = 2 * std::atan2(swing.GetZ(), swing.GetW());
            const auto angular = rotation.Conjugated() * bodies.GetAngularVelocity(second->GetID());
            const auto firstAngular = rotation.Conjugated() * bodies.GetAngularVelocity(first->GetID());
            const auto point = bodies.GetPosition(second->GetID()) + bodies.GetRotation(second->GetID()) * anchor;
            const auto force = joint->GetTotalLambdaPosition() / delta;
            const auto motor = joint->GetTotalLambdaMotor() / delta;
            std::cout << "swing " << caseId << ' ' << step << ' ' << twistAngle << ' ' << swingY << ' ' << swingZ
                << ' ' << angular.GetX() << ' ' << angular.GetY() << ' ' << angular.GetZ()
                << ' ' << firstAngular.GetX() << ' ' << (point - bodies.GetPosition(first->GetID())).Length()
                << ' ' << force.GetX() << ' ' << force.GetY() << ' ' << force.GetZ()
                << ' ' << motor.GetX() << ' ' << motor.GetY() << ' ' << motor.GetZ() << '\n';
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
    for (int caseId = 0; caseId < 12 && result == 0; ++caseId) result = Physics3D::runSwingTwistCase(caseId);
    JPH::UnregisterTypes();
    JPH::Factory::sInstance = nullptr;
    return result;
}
