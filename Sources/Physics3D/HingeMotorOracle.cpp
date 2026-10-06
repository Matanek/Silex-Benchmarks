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
#include <Jolt/Physics/Constraints/HingeConstraint.h>
#include <cmath>
#include <iostream>
#include <memory>

namespace Physics3D {

// -----------------------------------------------------------------------------

int runMotorCase(int caseId) {
    JPH::BroadPhaseLayerInterfaceTable broadPhase(1, 1);
    broadPhase.MapObjectToBroadPhaseLayer(0, JPH::BroadPhaseLayer(0));
    JPH::ObjectLayerPairFilterTable pairFilter(1);
    JPH::ObjectVsBroadPhaseLayerFilterTable phaseFilter(broadPhase, 1, pairFilter, 1);
    JPH::PhysicsSystem world;
    world.Init(16, 0, 16, 16, broadPhase, phaseFilter, pairFilter);
    auto physicsSettings = world.GetPhysicsSettings();
    physicsSettings.mNumVelocitySteps = 12;
    physicsSettings.mNumPositionSteps = 8;
    world.SetPhysicsSettings(physicsSettings);
    world.SetGravity(caseId == 4 ? JPH::Vec3(0, -9.81f, 0) : JPH::Vec3::sZero());
    JPH::RefConst<JPH::SphereShape> sphere = new JPH::SphereShape(0.5f);
    auto anchor = JPH::Vec3::sZero();
    auto position = JPH::RVec3::sZero();
    if (caseId == 4) { anchor = JPH::Vec3(0, 1, 0); position = JPH::RVec3(0, -1, 0); }
    JPH::BodyCreationSettings firstSettings(sphere, JPH::RVec3::sZero(), JPH::Quat::sIdentity(),
        caseId == 2 ? JPH::EMotionType::Dynamic : JPH::EMotionType::Static, 0);
    firstSettings.mAllowSleeping = false;
    firstSettings.mLinearDamping = firstSettings.mAngularDamping = 0;
    firstSettings.mOverrideMassProperties = JPH::EOverrideMassProperties::CalculateInertia;
    firstSettings.mMassPropertiesOverride.mMass = 1;
    JPH::BodyCreationSettings secondSettings(sphere, position, JPH::Quat::sIdentity(), JPH::EMotionType::Dynamic, 0);
    secondSettings.mAllowSleeping = false;
    secondSettings.mLinearDamping = secondSettings.mAngularDamping = 0;
    secondSettings.mOverrideMassProperties = JPH::EOverrideMassProperties::MassAndInertiaProvided;
    secondSettings.mMassPropertiesOverride.mMass = 1;
    const float inertia = caseId == 2 ? 0.4f : 0.1f;
    secondSettings.mMassPropertiesOverride.mInertia = JPH::Mat44::sScale(JPH::Vec3::sReplicate(inertia));
    auto& bodies = world.GetBodyInterface();
    auto* first = bodies.CreateBody(firstSettings);
    auto* second = bodies.CreateBody(secondSettings);
    if (!first || !second) return 3;
    bodies.AddBody(first->GetID(), caseId == 2 ? JPH::EActivation::Activate : JPH::EActivation::DontActivate);
    bodies.AddBody(second->GetID(), JPH::EActivation::Activate);
    float speed = 10.0f;
    float torque = 0.1f;
    if (caseId == 1) { speed = 1.0f; torque = 1.0f; }
    if (caseId == 2) speed = 1.0f;
    if (caseId == 3) { speed = 2.0f; torque = 0.4f; }
    if (caseId == 4) { speed = 1.0f; torque = 20.0f; }
    JPH::HingeConstraintSettings settings;
    settings.mSpace = JPH::EConstraintSpace::LocalToBodyCOM;
    settings.mPoint1 = JPH::RVec3::sZero();
    settings.mPoint2 = JPH::RVec3(anchor);
    settings.mHingeAxis1 = settings.mHingeAxis2 = JPH::Vec3::sAxisZ();
    settings.mNormalAxis1 = settings.mNormalAxis2 = JPH::Vec3::sAxisX();
    settings.mMotorSettings.SetTorqueLimit(torque);
    if (caseId == 3) { settings.mLimitsMin = -0.2f; settings.mLimitsMax = 0.3f; }
    JPH::Ref<JPH::HingeConstraint> joint = new JPH::HingeConstraint(*first, *second, settings);
    joint->SetTargetAngularVelocity(speed);
    joint->SetMotorState(JPH::EMotorState::Velocity);
    world.AddConstraint(joint.GetPtr());
    JPH::TempAllocatorImpl allocator(1024 * 1024);
    JPH::JobSystemSingleThreaded jobs(JPH::cMaxPhysicsJobs);
    constexpr float delta = 1.0f / 60.0f;
    for (int step = 1; step <= 120; ++step) {
        if (step == 61 && (caseId == 1 || caseId == 2 || caseId == 3)) joint->SetTargetAngularVelocity(-speed);
        if (step == 91 && caseId == 1) joint->SetMotorState(JPH::EMotorState::Off);
        if (world.Update(delta, 1, &allocator, &jobs) != JPH::EPhysicsUpdateError::None) return 4;
        if (step % 15 == 0) {
            const auto point = bodies.GetPosition(second->GetID());
            const auto orientation = bodies.GetRotation(second->GetID());
            const auto firstAxis = bodies.GetRotation(first->GetID()) * JPH::Vec3::sAxisZ();
            const auto secondAxis = orientation * JPH::Vec3::sAxisZ();
            const auto firstSpeed = bodies.GetAngularVelocity(first->GetID());
            const auto secondSpeed = bodies.GetAngularVelocity(second->GetID());
            const float axisError = std::atan2(firstAxis.Cross(secondAxis).Length(), firstAxis.Dot(secondAxis));
            std::cout << "motor " << caseId << ' ' << step << ' ' << point.GetX() << ' ' << point.GetY()
                << ' ' << joint->GetCurrentAngle() << ' ' << firstAxis.Dot(secondSpeed - firstSpeed)
                << ' ' << firstSpeed.GetZ() << ' ' << secondSpeed.GetZ() << ' ' << joint->GetTotalLambdaMotor() / delta
                << ' ' << (point + orientation * anchor - bodies.GetPosition(first->GetID())).Length()
                << ' ' << axisError << ' ' << joint->GetTotalLambdaPosition().GetY() / delta << '\n';
        }
    }
    world.RemoveConstraint(joint.GetPtr());
    bodies.RemoveBody(first->GetID());
    bodies.RemoveBody(second->GetID());
    bodies.DestroyBody(first->GetID());
    bodies.DestroyBody(second->GetID());
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
    for (int caseId = 0; caseId < 5 && result == 0; ++caseId) result = Physics3D::runMotorCase(caseId);
    JPH::UnregisterTypes();
    JPH::Factory::sInstance = nullptr;
    return result;
}
