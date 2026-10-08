#include <cmath>
#include <iostream>
#include <memory>
#include <numbers>
#include <Jolt/Jolt.h>
#include <Jolt/RegisterTypes.h>
#include <Jolt/Core/Factory.h>
#include <Jolt/Core/JobSystemSingleThreaded.h>
#include <Jolt/Core/TempAllocator.h>
#include <Jolt/Physics/PhysicsSystem.h>
#include <Jolt/Physics/Body/BodyCreationSettings.h>
#include <Jolt/Physics/Collision/BroadPhase/BroadPhaseLayerInterfaceTable.h>
#include <Jolt/Physics/Collision/ObjectLayerPairFilterTable.h>
#include <Jolt/Physics/Collision/BroadPhase/ObjectVsBroadPhaseLayerFilterTable.h>
#include <Jolt/Physics/Collision/Shape/PlaneShape.h>
#include <Jolt/Physics/Collision/Shape/SphereShape.h>
#include <Jolt/Physics/Constraints/FixedConstraint.h>
#include <Jolt/Physics/Constraints/HingeConstraint.h>

namespace Physics3D {

// -----------------------------------------------------------------------------

int runLoadedCase(int caseId) {
    const int frequency = caseId == 4 ? 120 : 60;
    const float offset = caseId == 5 ? -1 : caseId == 6 ? 0 : 1;
    JPH::BroadPhaseLayerInterfaceTable broadPhase(3, 1);
    for (JPH::ObjectLayer layer = 0; layer < 3; ++layer) broadPhase.MapObjectToBroadPhaseLayer(layer, JPH::BroadPhaseLayer(0));
    JPH::ObjectLayerPairFilterTable pairFilter(3);
    pairFilter.EnableCollision(0, 1);
    JPH::ObjectVsBroadPhaseLayerFilterTable phaseFilter(broadPhase, 3, pairFilter, 1);
    JPH::PhysicsSystem world;
    world.Init(16, 0, 16, 16, broadPhase, phaseFilter, pairFilter);
    auto options = world.GetPhysicsSettings();
    options.mNumVelocitySteps = 12;
    options.mNumPositionSteps = 4;
    world.SetPhysicsSettings(options);
    world.SetGravity(caseId == 2 || caseId == 3 ? JPH::Vec3::sZero() : JPH::Vec3(0, -9.81f, 0));
    auto& bodies = world.GetBodyInterface();
    JPH::RefConst<JPH::SphereShape> sphere = new JPH::SphereShape(0.5f);
    JPH::BodyID floorId;
    if (caseId != 1 && caseId != 3) {
        JPH::RefConst<JPH::PlaneShape> plane = new JPH::PlaneShape(JPH::Plane(JPH::Vec3::sAxisY(), 0));
        JPH::BodyCreationSettings settings(plane, JPH::RVec3(0, -1.5f, 0), JPH::Quat::sIdentity(), JPH::EMotionType::Static, 0);
        settings.mFriction = 0.6f;
        settings.mRestitution = 0;
        floorId = bodies.CreateAndAddBody(settings, JPH::EActivation::DontActivate);
        if (floorId.IsInvalid()) return 3;
    }
    auto makeBody = [&](JPH::Vec3 position, JPH::EMotionType type, JPH::ObjectLayer layer, float mass, float inertia) {
        JPH::BodyCreationSettings settings(sphere, JPH::RVec3(position), JPH::Quat::sIdentity(), type, layer);
        settings.mAllowSleeping = false;
        settings.mLinearDamping = settings.mAngularDamping = 0;
        settings.mFriction = 0.6f;
        settings.mRestitution = 0;
        settings.mOverrideMassProperties = JPH::EOverrideMassProperties::MassAndInertiaProvided;
        settings.mMassPropertiesOverride.mMass = mass;
        settings.mMassPropertiesOverride.mInertia = JPH::Mat44::sScale(JPH::Vec3::sReplicate(inertia));
        return bodies.CreateAndAddBody(settings, type == JPH::EMotionType::Static ? JPH::EActivation::DontActivate : JPH::EActivation::Activate);
    };
    constexpr float bodyMass = std::numbers::pi_v<float> / 6;
    const auto pivotId = makeBody(JPH::Vec3::sZero(), JPH::EMotionType::Static, 2, 1, 0.1f);
    const auto bodyId = makeBody(JPH::Vec3(0, -1, 0), JPH::EMotionType::Dynamic, 1, bodyMass, bodyMass * 0.1f);
    const auto payloadId = makeBody(JPH::Vec3(0, -1, offset), JPH::EMotionType::Dynamic, 2, 2, 0.2f);
    if (pivotId.IsInvalid() || bodyId.IsInvalid() || payloadId.IsInvalid()) return 3;
    JPH::FixedConstraintSettings fixedSettings;
    fixedSettings.mSpace = JPH::EConstraintSpace::LocalToBodyCOM;
    fixedSettings.mPoint1 = JPH::RVec3(0, 0, offset);
    fixedSettings.mPoint2 = JPH::RVec3::sZero();
    JPH::Ref<JPH::FixedConstraint> attachment = static_cast<JPH::FixedConstraint*>(bodies.CreateConstraint(&fixedSettings, bodyId, payloadId));
    world.AddConstraint(attachment.GetPtr());
    JPH::HingeConstraintSettings hingeSettings;
    hingeSettings.mSpace = JPH::EConstraintSpace::LocalToBodyCOM;
    hingeSettings.mPoint1 = JPH::RVec3::sZero();
    hingeSettings.mPoint2 = JPH::RVec3(0, 1, 0);
    hingeSettings.mHingeAxis1 = hingeSettings.mHingeAxis2 = JPH::Vec3::sAxisZ();
    hingeSettings.mNormalAxis1 = hingeSettings.mNormalAxis2 = JPH::Vec3::sAxisX();
    hingeSettings.mMotorSettings.SetTorqueLimits(-0.2f, 0.2f);
    JPH::Ref<JPH::HingeConstraint> joint = static_cast<JPH::HingeConstraint*>(bodies.CreateConstraint(&hingeSettings, pivotId, bodyId));
    joint->SetTargetAngularVelocity(0.25f);
    joint->SetMotorState(JPH::EMotorState::Velocity);
    world.AddConstraint(joint.GetPtr());
    JPH::TempAllocatorImpl allocator(1024 * 1024);
    JPH::JobSystemSingleThreaded jobs(JPH::cMaxPhysicsJobs);
    const float delta = 1.0f / frequency;
    for (int step = 1; step <= frequency * 3; ++step) {
        if (step == frequency * 3 / 2 + 1) joint->SetTargetAngularVelocity(-0.25f);
        if (world.Update(delta, 1, &allocator, &jobs) != JPH::EPhysicsUpdateError::None) return 4;
        const auto p = bodies.GetPosition(bodyId);
        const auto q = bodies.GetPosition(payloadId);
        const auto bodyRotation = bodies.GetRotation(bodyId);
        const auto payloadRotation = bodies.GetRotation(payloadId);
        const auto axis = bodyRotation * JPH::Vec3::sAxisZ();
        const auto difference = (payloadRotation * bodyRotation.Conjugated()).Normalized();
        const float fixedAngle = 2 * std::atan2(JPH::Vec3(difference.GetX(), difference.GetY(), difference.GetZ()).Length(), std::abs(difference.GetW()));
        const float axisError = std::atan2(JPH::Vec3::sAxisZ().Cross(axis).Length(), axis.GetZ());
        const auto b = axis.GetNormalizedPerpendicular();
        const auto c = axis.Cross(b);
        const auto rotationLambda = joint->GetTotalLambdaRotation();
        const float momentX = (b.Cross(JPH::Vec3::sAxisZ()) * rotationLambda[0]
            + c.Cross(JPH::Vec3::sAxisZ()) * rotationLambda[1]).GetX() / delta;
        std::cout << "loaded " << caseId << ' ' << step << ' ' << p.GetX() << ' ' << p.GetY() << ' ' << p.GetZ()
            << ' ' << q.GetX() << ' ' << q.GetY() << ' ' << q.GetZ() << ' ' << joint->GetCurrentAngle()
            << ' ' << bodies.GetAngularVelocity(bodyId).GetZ() << ' ' << joint->GetTotalLambdaMotor() / delta
            << ' ' << axisError << ' ' << (p + bodyRotation * JPH::Vec3::sAxisY()).Length()
            << ' ' << (q - p - bodyRotation * JPH::Vec3(0, 0, offset)).Length() << ' ' << fixedAngle
            << ' ' << joint->GetTotalLambdaPosition().GetY() / delta
            << ' ' << momentX
            << ' ' << attachment->GetTotalLambdaPosition().GetY() / delta << '\n';
    }
    world.RemoveConstraint(joint.GetPtr());
    world.RemoveConstraint(attachment.GetPtr());
    for (const auto id : {pivotId, bodyId, payloadId, floorId}) {
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
    for (int caseId = 0; caseId < 7 && result == 0; ++caseId) result = Physics3D::runLoadedCase(caseId);
    JPH::UnregisterTypes();
    JPH::Factory::sInstance = nullptr;
    return result;
}
