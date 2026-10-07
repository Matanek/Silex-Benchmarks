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
#include <Jolt/Physics/Constraints/SliderConstraint.h>

namespace Physics3D {

// -----------------------------------------------------------------------------

int runSliderMotorCase(int caseId) {
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
    auto gravity = JPH::Vec3(0, -9.81f, 0);
    if (caseId == 1 || caseId == 3) gravity = JPH::Vec3::sZero();
    if (caseId == 5) gravity = JPH::Vec3(-2, 0, 0);
    world.SetGravity(gravity);
    JPH::RefConst<JPH::SphereShape> sphere = new JPH::SphereShape(0.25f);
    auto firstType = JPH::EMotionType::Static;
    if (caseId == 1) firstType = JPH::EMotionType::Dynamic;
    if (caseId == 3) firstType = JPH::EMotionType::Kinematic;
    JPH::BodyCreationSettings firstSettings(sphere, JPH::RVec3::sZero(), JPH::Quat::sIdentity(), firstType, 0);
    firstSettings.mAllowSleeping = false;
    firstSettings.mLinearDamping = firstSettings.mAngularDamping = 0;
    firstSettings.mOverrideMassProperties = JPH::EOverrideMassProperties::MassAndInertiaProvided;
    firstSettings.mMassPropertiesOverride.mMass = 2;
    firstSettings.mMassPropertiesOverride.mInertia = JPH::Mat44::sScale(JPH::Vec3::sReplicate(0.2f));
    auto position = JPH::RVec3::sZero();
    auto anchor = JPH::Vec3::sZero();
    if (caseId == 2) { anchor = JPH::Vec3(0, 0.5f, 0); position = JPH::RVec3(0, -0.5f, 0); }
    if (caseId == 3) position = JPH::RVec3(1, 0, 0);
    if (caseId == 4) position = JPH::RVec3(0.5f, 0, 0);
    const float mass = caseId == 1 ? 8.0f : 2.0f;
    const float capacity = caseId == 1 ? 3.2f : 2.0f;
    JPH::BodyCreationSettings secondSettings(sphere, position, JPH::Quat::sIdentity(), JPH::EMotionType::Dynamic, 0);
    secondSettings.mAllowSleeping = false;
    secondSettings.mLinearDamping = secondSettings.mAngularDamping = 0;
    secondSettings.mOverrideMassProperties = JPH::EOverrideMassProperties::MassAndInertiaProvided;
    secondSettings.mMassPropertiesOverride.mMass = mass;
    secondSettings.mMassPropertiesOverride.mInertia = JPH::Mat44::sScale(JPH::Vec3::sReplicate(mass * 0.1f));
    auto& bodies = world.GetBodyInterface();
    auto* first = bodies.CreateBody(firstSettings);
    auto* second = bodies.CreateBody(secondSettings);
    if (!first || !second) return 3;
    bodies.AddBody(first->GetID(), caseId == 1 || caseId == 3 ? JPH::EActivation::Activate : JPH::EActivation::DontActivate);
    bodies.AddBody(second->GetID(), JPH::EActivation::Activate);
    JPH::SliderConstraintSettings settings;
    settings.mSpace = JPH::EConstraintSpace::LocalToBodyCOM;
    settings.mAutoDetectPoint = false;
    settings.mPoint1 = JPH::RVec3::sZero();
    settings.mPoint2 = JPH::RVec3(anchor);
    settings.mSliderAxis1 = settings.mSliderAxis2 = JPH::Vec3::sAxisX();
    settings.mNormalAxis1 = settings.mNormalAxis2 = JPH::Vec3::sAxisY();
    settings.mMotorSettings.SetForceLimit(capacity);
    if (caseId == 4) { settings.mLimitsMin = -0.5f; settings.mLimitsMax = 0.5f; }
    JPH::Ref<JPH::SliderConstraint> joint = new JPH::SliderConstraint(*first, *second, settings);
    joint->SetTargetVelocity(0.6f);
    joint->SetMotorState(JPH::EMotorState::Velocity);
    world.AddConstraint(joint.GetPtr());
    if (caseId == 3) {
        bodies.SetAngularVelocity(first->GetID(), JPH::Vec3(0, 0, 0.2f));
        bodies.SetAngularVelocity(second->GetID(), JPH::Vec3(0, 0, 0.2f));
        bodies.SetLinearVelocity(second->GetID(), JPH::Vec3(0.6f, 0.2f, 0));
    }
    JPH::TempAllocatorImpl allocator(1024 * 1024);
    JPH::JobSystemSingleThreaded jobs(JPH::cMaxPhysicsJobs);
    constexpr float delta = 1.0f / 120.0f;
    for (int step = 1; step <= 240; ++step) {
        if (caseId != 3 && caseId != 4 && caseId != 5) {
            if (step == 81) joint->SetTargetVelocity(-0.6f);
            if (step == 161) joint->SetTargetVelocity(0);
        }
        if (caseId == 4 && step == 121) {
            bodies.SetPosition(second->GetID(), JPH::RVec3(-0.5f, 0, 0), JPH::EActivation::Activate);
            bodies.SetLinearVelocity(second->GetID(), JPH::Vec3::sZero());
            joint->SetTargetVelocity(-0.6f);
        }
        if (world.Update(delta, 1, &allocator, &jobs) != JPH::EPhysicsUpdateError::None) return 4;
        if (step % 10 == 0) {
            const auto firstRotation = bodies.GetRotation(first->GetID());
            const auto secondRotation = bodies.GetRotation(second->GetID());
            const auto bodyPosition = bodies.GetPosition(second->GetID());
            const auto point = bodyPosition + secondRotation * anchor;
            const auto offset = JPH::Vec3(point - bodies.GetPosition(first->GetID()));
            const auto axis = firstRotation * JPH::Vec3::sAxisX();
            const auto firstRadius = JPH::Vec3(point - bodies.GetCenterOfMassPosition(first->GetID()));
            const auto secondRadius = JPH::Vec3(point - bodies.GetCenterOfMassPosition(second->GetID()));
            const auto firstAngular = bodies.GetAngularVelocity(first->GetID());
            const auto secondAngular = bodies.GetAngularVelocity(second->GetID());
            const auto firstVelocity = bodies.GetLinearVelocity(first->GetID());
            const auto secondVelocity = bodies.GetLinearVelocity(second->GetID());
            const auto relativeVelocity = secondVelocity + secondAngular.Cross(secondRadius)
                - firstVelocity - firstAngular.Cross(firstRadius);
            const auto difference = secondRotation * firstRotation.Conjugated();
            const float angleError = 2 * std::atan2(JPH::Vec3(difference.GetX(), difference.GetY(), difference.GetZ()).Length(), std::abs(difference.GetW()));
            const auto force = (firstRotation * JPH::Vec3::sAxisY()) * joint->GetTotalLambdaPosition()[0]
                + (firstRotation * JPH::Vec3::sAxisZ()) * joint->GetTotalLambdaPosition()[1]
                + axis * (joint->GetTotalLambdaPositionLimits() + joint->GetTotalLambdaMotor());
            std::cout << "slider-motor " << caseId << ' ' << step << ' ' << joint->GetCurrentPosition()
                << ' ' << relativeVelocity.Dot(axis) << ' ' << firstVelocity.GetX() << ' ' << secondVelocity.GetX()
                << ' ' << bodyPosition.GetX() << ' ' << bodyPosition.GetY() << ' ' << firstAngular.GetZ() << ' ' << secondAngular.GetZ()
                << ' ' << (offset - axis * offset.Dot(axis)).Length() << ' ' << angleError
                << ' ' << force.GetX() / delta << ' ' << force.GetY() / delta
                << ' ' << joint->GetTotalLambdaPositionLimits() / delta << ' ' << joint->GetTotalLambdaMotor() / delta
                << ' ' << joint->GetTotalLambdaRotation().GetZ() / delta << '\n';
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
    for (int caseId = 0; caseId < 6 && result == 0; ++caseId) result = Physics3D::runSliderMotorCase(caseId);
    JPH::UnregisterTypes();
    JPH::Factory::sInstance = nullptr;
    return result;
}
