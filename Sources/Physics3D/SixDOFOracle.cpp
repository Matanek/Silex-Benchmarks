#include <cmath>
#include <cstdlib>
#include <iostream>
#include <limits>
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
#include <Jolt/Physics/Constraints/SixDOFConstraint.h>

namespace Physics3D {

// -----------------------------------------------------------------------------

int runSixDOFCase(int caseId) {
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
    world.SetGravity((caseId == 8 || caseId == 10) ? JPH::Vec3(0, -9.81f, 0) : JPH::Vec3::sZero());
    JPH::RefConst<JPH::SphereShape> sphere = new JPH::SphereShape(0.25f);
    auto rotation = caseId == 11 ? JPH::Quat::sRotation(JPH::Vec3::sAxisY(), 0.7f) : JPH::Quat::sIdentity();
    auto firstType = caseId == 9 ? JPH::EMotionType::Dynamic : JPH::EMotionType::Static;
    JPH::BodyCreationSettings firstSettings(sphere, JPH::RVec3::sZero(), rotation, firstType, 0);
    firstSettings.mAllowSleeping = false;
    firstSettings.mLinearDamping = firstSettings.mAngularDamping = 0;
    firstSettings.mOverrideMassProperties = JPH::EOverrideMassProperties::MassAndInertiaProvided;
    firstSettings.mMassPropertiesOverride.mMass = 2;
    firstSettings.mMassPropertiesOverride.mInertia = JPH::Mat44::sScale(JPH::Vec3::sReplicate(0.2f));
    const float mass = caseId == 9 ? 8.0f : 2.0f;
    auto position = caseId == 10 ? JPH::RVec3(0, -1, 0) : JPH::RVec3::sZero();
    if (caseId == 8) position = JPH::RVec3(0, -0.8f, 0);
    auto anchor = caseId == 10 ? JPH::Vec3::sAxisY() : JPH::Vec3::sZero();
    JPH::BodyCreationSettings secondSettings(sphere, position, rotation, JPH::EMotionType::Dynamic, 0);
    if (caseId == 15) secondSettings.mRotation = JPH::Quat::sRotation(JPH::Vec3::sAxisY(), 0.3f);
    secondSettings.mAllowSleeping = false;
    secondSettings.mLinearDamping = secondSettings.mAngularDamping = 0;
    secondSettings.mOverrideMassProperties = JPH::EOverrideMassProperties::MassAndInertiaProvided;
    secondSettings.mMassPropertiesOverride.mMass = mass;
    secondSettings.mMassPropertiesOverride.mInertia = JPH::Mat44::sScale(JPH::Vec3::sReplicate(mass * 0.1f));
    auto& bodies = world.GetBodyInterface();
    auto* first = bodies.CreateBody(firstSettings);
    auto* second = bodies.CreateBody(secondSettings);
    if (!first || !second) return 3;
    bodies.AddBody(first->GetID(), caseId == 9 ? JPH::EActivation::Activate : JPH::EActivation::DontActivate);
    bodies.AddBody(second->GetID(), JPH::EActivation::Activate);
    JPH::SixDOFConstraintSettings settings;
    settings.mSpace = JPH::EConstraintSpace::LocalToBodyCOM;
    using Axis = JPH::SixDOFConstraintSettings::EAxis;
    settings.mPosition1 = JPH::RVec3::sZero();
    settings.mPosition2 = JPH::RVec3(anchor);
    if (caseId == 1 || caseId == 9) settings.MakeFixedAxis(Axis::TranslationX);
    if (caseId == 2 || caseId == 11 || caseId == 12) settings.SetLimitedAxis(Axis::TranslationX, -0.4f, 0.5f);
    if (caseId == 3 || caseId == 8) settings.SetLimitedAxis(Axis::TranslationY, -0.4f, 0.4f);
    if (caseId == 10) {
        settings.MakeFixedAxis(Axis::TranslationX);
        settings.MakeFixedAxis(Axis::TranslationY);
        settings.MakeFixedAxis(Axis::TranslationZ);
    }
    if (caseId == 13) {
        settings.SetLimitedAxis(Axis::RotationY, -0.3f, 0.3f);
        settings.SetLimitedAxis(Axis::RotationZ, -0.6f, 0.6f);
    }
    if (caseId == 15) {
        settings.mSwingType = JPH::ESwingType::Pyramid;
        settings.SetLimitedAxis(Axis::RotationY, 0.2f, 0.4f);
    }
    if (caseId == 6) settings.mMaxFriction[Axis::TranslationZ] = 2;
    if (caseId == 7) settings.mMaxFriction[Axis::RotationX] = 0.2f;
    if (caseId == 8) settings.mLimitsSpringSettings[Axis::TranslationY] =
        JPH::SpringSettings(JPH::ESpringMode::StiffnessAndDamping, 200, 14);
    if (caseId == 4) {
        auto& motor = settings.mMotorSettings[Axis::TranslationX];
        motor.mMinForceLimit = -100; motor.mMaxForceLimit = 100;
        motor.mSpringSettings = JPH::SpringSettings(JPH::ESpringMode::StiffnessAndDamping, 20, 8);
    }
    if (caseId == 5) {
        auto& motor = settings.mMotorSettings[Axis::RotationZ];
        motor.mMinTorqueLimit = -10; motor.mMaxTorqueLimit = 10;
        motor.mSpringSettings = JPH::SpringSettings(JPH::ESpringMode::StiffnessAndDamping, 2, 0.8f);
    }
    if (caseId == 14) {
        auto& motor = settings.mMotorSettings[Axis::TranslationX];
        motor.mMinForceLimit = 0.1f; motor.mMaxForceLimit = 0.2f;
    }
    JPH::Ref<JPH::SixDOFConstraint> joint = new JPH::SixDOFConstraint(*first, *second, settings);
    world.AddConstraint(joint.GetPtr());
    auto speed = JPH::Vec3::sZero();
    auto angular = JPH::Vec3::sZero();
    if (caseId == 0) { speed = JPH::Vec3(0.5f, 0, 0); angular = JPH::Vec3(0.5f, 0, 0); }
    if (caseId == 1) { speed = JPH::Vec3(1, 0.5f, 0); angular = JPH::Vec3(0.5f, 0, 0); }
    if (caseId == 2 || caseId == 11 || caseId == 12) speed = JPH::Vec3(1.7f, 0, 0);
    if (caseId == 3) speed = JPH::Vec3(0, -2, 0);
    if (caseId == 6) speed = JPH::Vec3(0, 0, 1);
    if (caseId == 7) angular = JPH::Vec3(1, 0, 0);
    if (caseId == 9) speed = JPH::Vec3(1, 0, 0);
    if (caseId == 15) angular = JPH::Vec3(0, -2, 0);
    if (caseId == 13) angular = JPH::Vec3(0, 1.7f, 0);
    if (caseId == 4) {
        joint->SetMotorState(Axis::TranslationX, JPH::EMotorState::PositionAndVelocity);
        joint->SetTargetPositionCS(JPH::Vec3(0.6f, 0, 0));
        joint->SetTargetVelocityCS(JPH::Vec3(0.1f, 0, 0));
    }
    if (caseId == 5) {
        joint->SetMotorState(Axis::RotationZ, JPH::EMotorState::PositionAndVelocity);
        joint->SetTargetOrientationCS(JPH::Quat::sRotation(JPH::Vec3::sAxisZ(), 0.6f));
        joint->SetTargetAngularVelocityCS(JPH::Vec3(0, 0, 0.1f));
    }
    if (caseId == 14) {
        joint->SetMotorState(Axis::TranslationX, JPH::EMotorState::Velocity);
        joint->SetTargetVelocityCS(JPH::Vec3(-0.5f, 0, 0));
    }
    bodies.SetLinearVelocity(second->GetID(), rotation * speed);
    bodies.SetAngularVelocity(second->GetID(), rotation * angular);
    JPH::TempAllocatorImpl allocator(1024 * 1024);
    JPH::JobSystemSingleThreaded jobs(JPH::cMaxPhysicsJobs);
    constexpr float delta = 1.0f / 60.0f;
    for (int step = 1; step <= 360; ++step) {
        if (caseId == 8 && step == 181) joint->SetLimitsSpringSettings(Axis::TranslationY,
            JPH::SpringSettings(JPH::ESpringMode::StiffnessAndDamping, 400, 20));
        if (caseId == 12 && step == 181) {
            joint->SetTranslationLimits(JPH::Vec3(-0.4f, -std::numeric_limits<float>::max(), -std::numeric_limits<float>::max()),
                JPH::Vec3(0.2f, std::numeric_limits<float>::max(), std::numeric_limits<float>::max()));
            joint->ResetWarmStart();
        }
        if (world.Update(delta, 1, &allocator, &jobs) != JPH::EPhysicsUpdateError::None) return 4;
        if (step % 15 == 0) {
            auto q = joint->GetRotationInConstraintSpace();
            JPH::Quat swing, twist; q.GetSwingTwist(swing, twist);
            if (swing.GetW() < 0) swing = -swing;
            if (twist.GetW() < 0) twist = -twist;
            const auto point = bodies.GetPosition(second->GetID()) + bodies.GetRotation(second->GetID()) * anchor;
            const auto positionCS = rotation.Conjugated() * JPH::Vec3(point - bodies.GetPosition(first->GetID()));
            const auto velocity = rotation.Conjugated() * bodies.GetLinearVelocity(second->GetID());
            const auto angularVelocity = rotation.Conjugated() * bodies.GetAngularVelocity(second->GetID());
            const auto firstVelocity = rotation.Conjugated() * bodies.GetLinearVelocity(first->GetID());
            const auto linearMotor = joint->GetTotalLambdaMotorTranslation() / delta;
            const auto angularMotor = joint->GetTotalLambdaMotorRotation() / delta;
            const auto force = joint->GetTotalLambdaPosition() / delta + linearMotor;
            std::cout << "six " << caseId << ' ' << step
                << ' ' << positionCS.GetX() << ' ' << positionCS.GetY() << ' ' << positionCS.GetZ()
                << ' ' << 2 * std::atan2(twist.GetX(), twist.GetW())
                << ' ' << 2 * std::atan2(swing.GetY(), swing.GetW())
                << ' ' << 2 * std::atan2(swing.GetZ(), swing.GetW())
                << ' ' << velocity.GetX() << ' ' << velocity.GetY() << ' ' << velocity.GetZ()
                << ' ' << angularVelocity.GetX() << ' ' << angularVelocity.GetY() << ' ' << angularVelocity.GetZ()
                << ' ' << firstVelocity.GetX()
                << ' ' << force.GetX() << ' ' << force.GetY() << ' ' << force.GetZ()
                << ' ' << linearMotor.GetX() << ' ' << linearMotor.GetY() << ' ' << linearMotor.GetZ()
                << ' ' << angularMotor.GetX() << ' ' << angularMotor.GetY() << ' ' << angularMotor.GetZ() << '\n';
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
    for (int caseId = 0; caseId < 16 && result == 0; ++caseId) result = Physics3D::runSixDOFCase(caseId);
    JPH::UnregisterTypes();
    JPH::Factory::sInstance = nullptr;
    return result;
}
