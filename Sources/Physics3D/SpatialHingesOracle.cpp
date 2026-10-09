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
#include <Jolt/Physics/Constraints/HingeConstraint.h>

namespace Physics3D {

// -----------------------------------------------------------------------------

void writeVector(JPH::Vec3Arg value) {
    std::cout << ' ' << value.GetX() << ' ' << value.GetY() << ' ' << value.GetZ();
}

void writeQuaternion(JPH::QuatArg value) {
    std::cout << ' ' << value.GetX() << ' ' << value.GetY() << ' ' << value.GetZ() << ' ' << value.GetW();
}

JPH::Vec3 reactionTorque(const JPH::HingeConstraint& joint, JPH::Vec3Arg firstAxis, JPH::Vec3Arg secondAxis, float delta) {
    const auto b = secondAxis.GetNormalizedPerpendicular();
    const auto c = secondAxis.Cross(b);
    const auto lambda = joint.GetTotalLambdaRotation();
    return (b.Cross(firstAxis) * lambda[0] + c.Cross(firstAxis) * lambda[1]
        + firstAxis * joint.GetTotalLambdaMotor()) / delta;
}

float axisError(JPH::Vec3Arg first, JPH::Vec3Arg second) {
    return std::atan2(first.Cross(second).Length(), first.Dot(second));
}

// -----------------------------------------------------------------------------

int runSpatial(int mode, int massId, int rate, int side) {
    const float delta = 1.0f / static_cast<float>(rate);
    const float sign = static_cast<float>(side);
    const float mass = static_cast<float>(massId + 1);
    JPH::BroadPhaseLayerInterfaceTable broadPhase(1, 1);
    broadPhase.MapObjectToBroadPhaseLayer(0, JPH::BroadPhaseLayer(0));
    JPH::ObjectLayerPairFilterTable pairFilter(1);
    JPH::ObjectVsBroadPhaseLayerFilterTable phaseFilter(broadPhase, 1, pairFilter, 1);
    JPH::PhysicsSystem world;
    world.Init(16, 0, 16, 16, broadPhase, phaseFilter, pairFilter);
    auto settings = world.GetPhysicsSettings();
    settings.mNumVelocitySteps = 24;
    settings.mNumPositionSteps = 8;
    world.SetPhysicsSettings(settings);
    world.SetGravity(JPH::Vec3(0, -9.81f, 0));
    JPH::RefConst<JPH::SphereShape> sphere = new JPH::SphereShape(0.15f);
    auto& bodies = world.GetBodyInterface();
    JPH::BodyCreationSettings pivotSettings(sphere, JPH::RVec3::sZero(), JPH::Quat::sIdentity(), JPH::EMotionType::Static, 0);
    const auto pivot = bodies.CreateAndAddBody(pivotSettings, JPH::EActivation::DontActivate);
    JPH::BodyCreationSettings armSettings(sphere, JPH::RVec3(0.5f, 0, 0), JPH::Quat::sIdentity(), JPH::EMotionType::Dynamic, 0);
    armSettings.mAllowSleeping = false;
    armSettings.mLinearDamping = armSettings.mAngularDamping = 0;
    armSettings.mOverrideMassProperties = JPH::EOverrideMassProperties::MassAndInertiaProvided;
    armSettings.mMassPropertiesOverride.mMass = 2;
    armSettings.mMassPropertiesOverride.mInertia = JPH::Mat44::sScale(JPH::Vec3::sReplicate(0.4f));
    const auto arm = bodies.CreateAndAddBody(armSettings, JPH::EActivation::Activate);
    JPH::BodyCreationSettings payloadSettings(sphere, JPH::RVec3(1, 0, 0.8f * sign), JPH::Quat::sIdentity(), JPH::EMotionType::Dynamic, 0);
    payloadSettings.mAllowSleeping = false;
    payloadSettings.mLinearDamping = payloadSettings.mAngularDamping = 0;
    payloadSettings.mOverrideMassProperties = JPH::EOverrideMassProperties::MassAndInertiaProvided;
    payloadSettings.mMassPropertiesOverride.mMass = mass;
    payloadSettings.mMassPropertiesOverride.mInertia = JPH::Mat44::sScale(JPH::Vec3::sReplicate(0.2f));
    const auto payload = bodies.CreateAndAddBody(payloadSettings, JPH::EActivation::Activate);
    if (pivot.IsInvalid() || arm.IsInvalid() || payload.IsInvalid()) return 3;
    JPH::HingeConstraintSettings firstSettings;
    firstSettings.mSpace = JPH::EConstraintSpace::LocalToBodyCOM;
    firstSettings.mPoint1 = JPH::RVec3::sZero();
    firstSettings.mPoint2 = JPH::RVec3(-0.5f, 0, 0);
    firstSettings.mHingeAxis1 = firstSettings.mHingeAxis2 = JPH::Vec3::sAxisZ();
    firstSettings.mNormalAxis1 = firstSettings.mNormalAxis2 = JPH::Vec3::sAxisX();
    firstSettings.mMotorSettings.mMinTorqueLimit = -60;
    firstSettings.mMotorSettings.mMaxTorqueLimit = 60;
    JPH::Ref<JPH::HingeConstraint> first = static_cast<JPH::HingeConstraint*>(bodies.CreateConstraint(&firstSettings, pivot, arm));
    first->SetTargetAngularVelocity(0);
    first->SetMotorState(JPH::EMotorState::Velocity);
    world.AddConstraint(first.GetPtr());
    JPH::HingeConstraintSettings secondSettings;
    secondSettings.mSpace = JPH::EConstraintSpace::LocalToBodyCOM;
    secondSettings.mPoint1 = JPH::RVec3(0.5f, 0, 0);
    secondSettings.mPoint2 = JPH::RVec3(0, 0, -0.8f * sign);
    secondSettings.mHingeAxis1 = secondSettings.mHingeAxis2 = JPH::Vec3::sAxisX();
    secondSettings.mNormalAxis1 = secondSettings.mNormalAxis2 = JPH::Vec3::sAxisY();
    secondSettings.mMotorSettings.mMinTorqueLimit = -40;
    secondSettings.mMotorSettings.mMaxTorqueLimit = 40;
    JPH::Ref<JPH::HingeConstraint> second = static_cast<JPH::HingeConstraint*>(bodies.CreateConstraint(&secondSettings, arm, payload));
    second->SetTargetAngularVelocity(mode == 1 ? 0.2f * sign : 0);
    second->SetMotorState(JPH::EMotorState::Velocity);
    world.AddConstraint(second.GetPtr());
    JPH::TempAllocatorImpl allocator(1024 * 1024);
    JPH::JobSystemSingleThreaded jobs(JPH::cMaxPhysicsJobs);
    for (int step = 1; step <= rate * 2; ++step) {
        if (mode == 1 && step == rate * 2 / 3 + 1) second->SetTargetAngularVelocity(-0.2f * sign);
        if (mode == 1 && step == rate * 4 / 3 + 1) second->SetTargetAngularVelocity(0);
        const auto bp1 = bodies.GetPosition(arm);
        const auto bv1 = bodies.GetLinearVelocity(arm);
        const auto bw1 = bodies.GetAngularVelocity(arm);
        const auto bq1 = bodies.GetRotation(arm);
        const auto bp2 = bodies.GetPosition(payload);
        const auto bv2 = bodies.GetLinearVelocity(payload);
        const auto bw2 = bodies.GetAngularVelocity(payload);
        const auto bq2 = bodies.GetRotation(payload);
        const auto beforeAxis = bq1 * JPH::Vec3::sAxisX();
        if (beforeAxis.Dot(bq2 * JPH::Vec3::sAxisX()) <= 0.001f) return 5;
        if (world.Update(delta, 1, &allocator, &jobs) != JPH::EPhysicsUpdateError::None) return 4;
        const auto p1 = bodies.GetPosition(arm);
        const auto v1 = bodies.GetLinearVelocity(arm);
        const auto w1 = bodies.GetAngularVelocity(arm);
        const auto q1 = bodies.GetRotation(arm);
        const auto p2 = bodies.GetPosition(payload);
        const auto v2 = bodies.GetLinearVelocity(payload);
        const auto w2 = bodies.GetAngularVelocity(payload);
        const auto q2 = bodies.GetRotation(payload);
        std::cout << "spatialhinges " << mode << ' ' << massId << ' ' << rate << ' ' << side << ' ' << step;
        writeVector(JPH::Vec3(p1)); writeVector(v1); writeVector(w1); writeQuaternion(q1);
        writeVector(JPH::Vec3(p2)); writeVector(v2); writeVector(w2); writeQuaternion(q2);
        writeVector(JPH::Vec3(bp1)); writeVector(bv1); writeVector(bw1); writeQuaternion(bq1);
        writeVector(JPH::Vec3(bp2)); writeVector(bv2); writeVector(bw2); writeQuaternion(bq2);
        writeVector(first->GetTotalLambdaPosition() / delta);
        writeVector(reactionTorque(*first, JPH::Vec3::sAxisZ(), bq1 * JPH::Vec3::sAxisZ(), delta));
        writeVector(second->GetTotalLambdaPosition() / delta);
        writeVector(reactionTorque(*second, beforeAxis, bq2 * JPH::Vec3::sAxisX(), delta));
        std::cout << ' ' << first->GetCurrentAngle() << ' ' << w1.GetZ() << ' ' << first->GetTotalLambdaMotor() / delta
            << ' ' << JPH::Vec3(p1 + q1 * JPH::Vec3(-0.5f, 0, 0)).Length()
            << ' ' << axisError(JPH::Vec3::sAxisZ(), q1 * JPH::Vec3::sAxisZ())
            << ' ' << second->GetCurrentAngle() << ' ' << (w2 - w1).Dot(q1 * JPH::Vec3::sAxisX())
            << ' ' << second->GetTotalLambdaMotor() / delta
            << ' ' << JPH::Vec3(p2 + q2 * JPH::Vec3(0, 0, -0.8f * sign) - p1 - q1 * JPH::Vec3(0.5f, 0, 0)).Length()
            << ' ' << axisError(q1 * JPH::Vec3::sAxisX(), q2 * JPH::Vec3::sAxisX()) << '\n';
    }
    world.RemoveConstraint(second.GetPtr()); world.RemoveConstraint(first.GetPtr());
    for (const auto id : {payload, arm, pivot}) { bodies.RemoveBody(id); bodies.DestroyBody(id); }
    return 0;
}

// -----------------------------------------------------------------------------

} // namespace Physics3D

int main() {
#ifdef JPH_ENABLE_ASSERTS
    JPH::AssertFailed = [](const char* expression, const char*, const char* file, JPH::uint line) {
        std::cerr << expression << " at " << file << ':' << line << '\n';
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
    for (int mode : {0, 1}) { for (int mass : {0, 1}) { for (int rate : {60, 120}) { for (int side : {-1, 1}) {
        if (result == 0) result = Physics3D::runSpatial(mode, mass, rate, side);
    } } } }
    JPH::UnregisterTypes();
    JPH::Factory::sInstance = nullptr;
    return result;
}
