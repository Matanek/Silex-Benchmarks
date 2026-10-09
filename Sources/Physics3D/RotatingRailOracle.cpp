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

int runRail(int kind, int rate, int rotation) {
    const float delta = 1.0f / static_cast<float>(rate);
    const float omega = rotation == 1 ? 0.2f : rotation == 2 ? -0.2f : 0;
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
    JPH::BodyCreationSettings firstSettings(sphere, JPH::RVec3::sZero(), JPH::Quat::sIdentity(), JPH::EMotionType::Kinematic, 0);
    firstSettings.mAngularVelocity = JPH::Vec3(0, 0, omega);
    firstSettings.mAllowSleeping = false;
    firstSettings.mLinearDamping = firstSettings.mAngularDamping = 0;
    JPH::BodyCreationSettings bodySettings(sphere, JPH::RVec3(1, 0, 0), JPH::Quat::sIdentity(), JPH::EMotionType::Dynamic, 0);
    bodySettings.mAllowSleeping = false;
    bodySettings.mLinearDamping = bodySettings.mAngularDamping = 0;
    bodySettings.mLinearVelocity = JPH::Vec3(0, omega, 0);
    bodySettings.mAngularVelocity = JPH::Vec3(0, 0, omega);
    bodySettings.mOverrideMassProperties = JPH::EOverrideMassProperties::MassAndInertiaProvided;
    bodySettings.mMassPropertiesOverride.mMass = 2;
    bodySettings.mMassPropertiesOverride.mInertia = JPH::Mat44::sScale(JPH::Vec3::sReplicate(0.2f));
    auto& bodies = world.GetBodyInterface();
    auto* first = bodies.CreateBody(firstSettings);
    auto* body = bodies.CreateBody(bodySettings);
    if (!first || !body) return 3;
    bodies.AddBody(first->GetID(), JPH::EActivation::Activate);
    bodies.AddBody(body->GetID(), JPH::EActivation::Activate);
    JPH::SliderConstraintSettings settings;
    settings.mSpace = JPH::EConstraintSpace::LocalToBodyCOM;
    settings.mAutoDetectPoint = false;
    settings.mPoint1 = settings.mPoint2 = JPH::RVec3::sZero();
    settings.mSliderAxis1 = settings.mSliderAxis2 = JPH::Vec3::sAxisX();
    settings.mNormalAxis1 = settings.mNormalAxis2 = JPH::Vec3::sAxisY();
    settings.mMotorSettings.mMinForceLimit = -2;
    settings.mMotorSettings.mMaxForceLimit = 2;
    JPH::Ref<JPH::SliderConstraint> joint = new JPH::SliderConstraint(*first, *body, settings);
    if (kind == 1) { joint->SetTargetVelocity(0.6f); joint->SetMotorState(JPH::EMotorState::Velocity); }
    world.AddConstraint(joint.GetPtr());
    JPH::TempAllocatorImpl allocator(1024 * 1024);
    JPH::JobSystemSingleThreaded jobs(JPH::cMaxPhysicsJobs);
    for (int step = 1; step <= rate * 2; ++step) {
        if (kind == 1 && step == rate * 2 / 3 + 1) joint->SetTargetVelocity(-0.6f);
        if (kind == 1 && step == rate * 4 / 3 + 1) joint->SetTargetVelocity(0);
        const auto beforeVelocity = bodies.GetLinearVelocity(body->GetID());
        const auto beforeRotation = bodies.GetRotation(first->GetID());
        if (world.Update(delta, 1, &allocator, &jobs) != JPH::EPhysicsUpdateError::None) return 4;
        const auto afterRotation = bodies.GetRotation(first->GetID());
        const auto axis = afterRotation * JPH::Vec3::sAxisX();
        const auto position = bodies.GetPosition(body->GetID());
        const auto velocity = bodies.GetLinearVelocity(body->GetID());
        const auto offset = JPH::Vec3(position - bodies.GetPosition(first->GetID()));
        const auto relative = velocity - JPH::Vec3(0, 0, omega).Cross(offset);
        const auto lambda = JPH::Vec3(joint->GetTotalLambdaPositionLimits() + joint->GetTotalLambdaMotor(), joint->GetTotalLambdaPosition()[0], joint->GetTotalLambdaPosition()[1]);
        const auto force = beforeRotation * lambda / delta;
        const auto endForce = afterRotation * lambda / delta;
        const auto difference = bodies.GetRotation(body->GetID()) * afterRotation.Conjugated();
        const float angleError = 2 * std::atan2(JPH::Vec3(difference.GetX(), difference.GetY(), difference.GetZ()).Length(), std::abs(difference.GetW()));
        std::cout << "rail " << kind << ' ' << rate << ' ' << rotation << ' ' << step
            << ' ' << joint->GetCurrentPosition() << ' ' << relative.Dot(axis) << ' ' << position.GetX() << ' ' << position.GetY()
            << ' ' << velocity.GetX() << ' ' << velocity.GetY() << ' ' << beforeVelocity.GetX() << ' ' << beforeVelocity.GetY()
            << ' ' << force.GetX() << ' ' << force.GetY() << ' ' << endForce.GetX() << ' ' << endForce.GetY()
            << ' ' << joint->GetTotalLambdaMotor() / delta << ' ' << bodies.GetAngularVelocity(body->GetID()).GetZ()
            << ' ' << (offset - axis * offset.Dot(axis)).Length() << ' ' << angleError << ' ' << axis.GetX() << ' ' << axis.GetY() << '\n';
    }
    world.RemoveConstraint(joint.GetPtr());
    const auto firstId = first->GetID(); const auto bodyId = body->GetID();
    bodies.RemoveBody(firstId); bodies.RemoveBody(bodyId);
    bodies.DestroyBody(firstId); bodies.DestroyBody(bodyId);
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
    for (int kind : {0, 1}) {
        for (int rate : {60, 120}) {
            for (int rotation : {0, 1, 2}) {
                if (result == 0) result = Physics3D::runRail(kind, rate, rotation);
            }
        }
    }
    JPH::UnregisterTypes();
    JPH::Factory::sInstance = nullptr;
    return result;
}
