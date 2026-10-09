#include <algorithm>
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
#include <Jolt/Physics/Collision/Shape/PlaneShape.h>
#include <Jolt/Physics/Constraints/HingeConstraint.h>
#include <Jolt/Physics/Collision/ContactListener.h>

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

struct ContactWitness : JPH::ContactListener {
    JPH::BodyID payload;
    JPH::Vec3 point { JPH::Vec3::sZero() };
    JPH::Vec3 lever { JPH::Vec3::sZero() };
    int count { 0 };
    void capture(const JPH::Body& first, const JPH::Body& second, const JPH::ContactManifold& manifold);
    void OnContactAdded(const JPH::Body& first, const JPH::Body& second, const JPH::ContactManifold& manifold, JPH::ContactSettings&) override;
    void OnContactPersisted(const JPH::Body& first, const JPH::Body& second, const JPH::ContactManifold& manifold, JPH::ContactSettings&) override;
};

// -----------------------------------------------------------------------------

inline void ContactWitness::capture(const JPH::Body& first, const JPH::Body& second, const JPH::ContactManifold& manifold) {
    ++count;
    if ((first.GetID() != payload && second.GetID() != payload)
        || manifold.mRelativeContactPointsOn1.size() != 1 || manifold.mRelativeContactPointsOn2.size() != 1
        || std::abs(std::abs(manifold.mWorldSpaceNormal.GetY()) - 1.0f) > 0.000001f) std::abort();
    const auto midpoint = 0.5f * (manifold.GetWorldSpaceContactPointOn1(0) + manifold.GetWorldSpaceContactPointOn2(0));
    point = JPH::Vec3(midpoint);
    lever = JPH::Vec3(midpoint - (first.GetID() == payload ? first : second).GetCenterOfMassPosition());
}

inline void ContactWitness::OnContactAdded(const JPH::Body& first, const JPH::Body& second, const JPH::ContactManifold& manifold, JPH::ContactSettings&) {
    capture(first, second, manifold);
}

inline void ContactWitness::OnContactPersisted(const JPH::Body& first, const JPH::Body& second, const JPH::ContactManifold& manifold, JPH::ContactSettings&) {
    capture(first, second, manifold);
}

// -----------------------------------------------------------------------------

int runSpatialContact(int mode, int massId, int rate, int side) {
    const float delta = 1.0f / static_cast<float>(rate);
    const float sign = static_cast<float>(side);
    const float mass = static_cast<float>(massId + 1);
    constexpr JPH::uint k_objectLayers = 3;
    constexpr JPH::uint k_broadPhaseLayers = 1;
    JPH::BroadPhaseLayerInterfaceTable broadPhase(k_objectLayers, k_broadPhaseLayers);
    for (JPH::ObjectLayer layer : {0, 1, 2}) broadPhase.MapObjectToBroadPhaseLayer(layer, JPH::BroadPhaseLayer(0));
    JPH::ObjectLayerPairFilterTable pairFilter(k_objectLayers);
    pairFilter.EnableCollision(1, 2);
    JPH::ObjectVsBroadPhaseLayerFilterTable phaseFilter(broadPhase, k_broadPhaseLayers, pairFilter, k_objectLayers);
    if (!pairFilter.ShouldCollide(1, 2) || !phaseFilter.ShouldCollide(1, JPH::BroadPhaseLayer(0))) return 5;
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
    JPH::BodyCreationSettings payloadSettings(sphere, JPH::RVec3(1, 0, 0.8f * sign), JPH::Quat::sIdentity(), JPH::EMotionType::Dynamic, 1);
    payloadSettings.mAllowSleeping = false;
    payloadSettings.mFriction = payloadSettings.mRestitution = 0;
    payloadSettings.mLinearDamping = payloadSettings.mAngularDamping = 0;
    payloadSettings.mOverrideMassProperties = JPH::EOverrideMassProperties::MassAndInertiaProvided;
    payloadSettings.mMassPropertiesOverride.mMass = mass;
    payloadSettings.mMassPropertiesOverride.mInertia = JPH::Mat44::sScale(JPH::Vec3::sReplicate(0.2f));
    const auto payload = bodies.CreateAndAddBody(payloadSettings, JPH::EActivation::Activate);
    if (pivot.IsInvalid() || arm.IsInvalid() || payload.IsInvalid()) return 3;
    ContactWitness witness;
    witness.payload = payload;
    world.SetContactListener(&witness);
    JPH::BodyID floor;
    if (mode == 1) {
        JPH::RefConst<JPH::PlaneShape> plane = new JPH::PlaneShape(JPH::Plane(JPH::Vec3::sAxisY(), 0.22f));
        JPH::BodyCreationSettings floorSettings(plane, JPH::RVec3::sZero(), JPH::Quat::sIdentity(), JPH::EMotionType::Static, 2);
        floorSettings.mFriction = floorSettings.mRestitution = 0;
        floor = bodies.CreateAndAddBody(floorSettings, JPH::EActivation::DontActivate);
        if (floor.IsInvalid()) return 3;
    }
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
    second->SetTargetAngularVelocity(0.2f * sign);
    second->SetMotorState(JPH::EMotorState::Velocity);
    world.AddConstraint(second.GetPtr());
    JPH::TempAllocatorImpl allocator(1024 * 1024);
    JPH::JobSystemSingleThreaded jobs(JPH::cMaxPhysicsJobs);
    for (int step = 1; step <= rate * 2; ++step) {
        if (step == rate * 2 / 3 + 1) second->SetTargetAngularVelocity(-0.2f * sign);
        if (step == rate * 4 / 3 + 1) second->SetTargetAngularVelocity(0);
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
        witness.count = 0;
        witness.point = witness.lever = JPH::Vec3::sZero();
        if (world.Update(delta, 1, &allocator, &jobs) != JPH::EPhysicsUpdateError::None) return 4;
        const auto p1 = bodies.GetPosition(arm);
        const auto v1 = bodies.GetLinearVelocity(arm);
        const auto w1 = bodies.GetAngularVelocity(arm);
        const auto q1 = bodies.GetRotation(arm);
        const auto p2 = bodies.GetPosition(payload);
        const auto v2 = bodies.GetLinearVelocity(payload);
        const auto w2 = bodies.GetAngularVelocity(payload);
        const auto q2 = bodies.GetRotation(payload);
        const int contact = !floor.IsInvalid() && world.WereBodiesInContact(floor, payload) ? 1 : 0;
        if (witness.count != contact) return 5;
        const float inferred = mass * (v2.GetY() - bv2.GetY()) - second->GetTotalLambdaPosition().GetY() + mass * 9.81f * delta;
        const float penetration = std::max(0.0f, -0.07f - static_cast<float>(p2.GetY()));
        std::cout << "spatialcontacts " << mode << ' ' << massId << ' ' << rate << ' ' << side << ' ' << step;
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
            << ' ' << axisError(q1 * JPH::Vec3::sAxisX(), q2 * JPH::Vec3::sAxisX())
            << ' ' << 0 << ' ' << inferred << ' ' << 0 << ' ' << contact << ' ' << penetration << ' ' << 0;
        writeVector(witness.point); writeVector(witness.lever); std::cout << ' ' << witness.count << '\n';
    }
    world.RemoveConstraint(second.GetPtr()); world.RemoveConstraint(first.GetPtr());
    if (!floor.IsInvalid()) { bodies.RemoveBody(floor); bodies.DestroyBody(floor); }
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
        if (result == 0) result = Physics3D::runSpatialContact(mode, mass, rate, side);
    } } } }
    JPH::UnregisterTypes();
    JPH::Factory::sInstance = nullptr;
    return result;
}
