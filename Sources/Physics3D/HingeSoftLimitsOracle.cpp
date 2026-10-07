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

int runSoftCase(int caseId) {
    JPH::BroadPhaseLayerInterfaceTable broadPhase(1, 1);
    broadPhase.MapObjectToBroadPhaseLayer(0, JPH::BroadPhaseLayer(0));
    JPH::ObjectLayerPairFilterTable pairFilter(1);
    JPH::ObjectVsBroadPhaseLayerFilterTable phaseFilter(broadPhase, 1, pairFilter, 1);
    JPH::PhysicsSystem world;
    world.Init(16, 0, 16, 16, broadPhase, phaseFilter, pairFilter);
    auto physicsSettings = world.GetPhysicsSettings();
    physicsSettings.mNumVelocitySteps = 64;
    physicsSettings.mNumPositionSteps = 8;
    world.SetPhysicsSettings(physicsSettings);
    world.SetGravity(JPH::Vec3::sZero());
    JPH::RefConst<JPH::SphereShape> sphere = new JPH::SphereShape(0.5f);
    auto anchor = caseId == 5 ? JPH::Vec3(0, 1, 0) : JPH::Vec3::sZero();
    float angle = 0.4f, stiffness = 1.6f, damping = 0.8f;
    float minimum = 0.1f, maximum = 0.1f, speed = 0.0f;
    if (caseId == 1) { minimum = maximum = 0.0f; damping = 0.0f; }
    if (caseId == 2 || caseId == 3) { angle = 0.0f; minimum = -0.205f; maximum = 0.205f; speed = caseId == 2 ? 1.0f : -1.0f; }
    if (caseId == 4) { minimum = maximum = 0.0f; damping = 0.4f; }
    if (caseId == 5) { minimum = maximum = 0.2f; stiffness = 17.6f; damping = 8.8f; }
    if (caseId == 6) { angle = 0.0f; minimum = -0.3f; maximum = 0.3f; }
    if (caseId == 7) minimum = maximum = 0.0f;
    const auto rotation = JPH::Quat::sRotation(JPH::Vec3::sAxisZ(), angle);
    const auto position = JPH::RVec3(-(rotation * anchor));
    JPH::BodyCreationSettings firstSettings(sphere, JPH::RVec3::sZero(), JPH::Quat::sIdentity(),
        caseId == 4 ? JPH::EMotionType::Dynamic : JPH::EMotionType::Static, 0);
    firstSettings.mAllowSleeping = false;
    firstSettings.mLinearDamping = firstSettings.mAngularDamping = 0;
    firstSettings.mOverrideMassProperties = JPH::EOverrideMassProperties::CalculateInertia;
    firstSettings.mMassPropertiesOverride.mMass = 1;
    JPH::BodyCreationSettings secondSettings(sphere, position, rotation, JPH::EMotionType::Dynamic, 0);
    secondSettings.mAllowSleeping = false;
    secondSettings.mLinearDamping = secondSettings.mAngularDamping = 0;
    secondSettings.mOverrideMassProperties = JPH::EOverrideMassProperties::MassAndInertiaProvided;
    secondSettings.mMassPropertiesOverride.mMass = 1;
    secondSettings.mMassPropertiesOverride.mInertia = JPH::Mat44::sScale(JPH::Vec3::sReplicate(caseId == 4 ? 0.4f : 0.1f));
    auto& bodies = world.GetBodyInterface();
    auto* first = bodies.CreateBody(firstSettings);
    auto* second = bodies.CreateBody(secondSettings);
    if (!first || !second) return 3;
    bodies.AddBody(first->GetID(), caseId == 4 ? JPH::EActivation::Activate : JPH::EActivation::DontActivate);
    bodies.AddBody(second->GetID(), JPH::EActivation::Activate);
    const float referenceAngle = caseId == 0 ? 0.1f : (caseId == 5 ? 0.2f : 0.0f);
    JPH::HingeConstraintSettings settings;
    settings.mSpace = JPH::EConstraintSpace::LocalToBodyCOM;
    settings.mPoint1 = JPH::RVec3::sZero();
    settings.mPoint2 = JPH::RVec3(anchor);
    settings.mHingeAxis1 = settings.mHingeAxis2 = JPH::Vec3::sAxisZ();
    settings.mNormalAxis1 = JPH::Vec3::sAxisX();
    settings.mNormalAxis2 = JPH::Quat::sRotation(JPH::Vec3::sAxisZ(), -referenceAngle) * JPH::Vec3::sAxisX();
    settings.mLimitsMin = minimum - referenceAngle;
    settings.mLimitsMax = maximum - referenceAngle;
    settings.mLimitsSpringSettings = JPH::SpringSettings(JPH::ESpringMode::StiffnessAndDamping, stiffness, damping);
    settings.mMotorSettings.SetTorqueLimits(-0.1f, 0.2f);
    JPH::Ref<JPH::HingeConstraint> joint = new JPH::HingeConstraint(*first, *second, settings);
    bodies.SetAngularVelocity(second->GetID(), JPH::Vec3(0, 0, speed));
    if (caseId == 6) { joint->SetTargetAngularVelocity(1.0f); joint->SetMotorState(JPH::EMotorState::Velocity); }
    world.AddConstraint(joint.GetPtr());
    JPH::TempAllocatorImpl allocator(1024 * 1024);
    JPH::JobSystemSingleThreaded jobs(JPH::cMaxPhysicsJobs);
    constexpr float delta = 1.0f / 60.0f;
    for (int step = 1; step <= 360; ++step) {
        if (caseId == 6 && step == 181) joint->SetTargetAngularVelocity(-1.0f);
        if (caseId == 7 && step == 121) {
            joint->SetLimitsSpringSettings(JPH::SpringSettings(JPH::ESpringMode::StiffnessAndDamping, 3.2f, 0.4f));
            joint->SetLimits(0.0f, 0.0f);
            bodies.SetPositionAndRotation(second->GetID(), JPH::RVec3::sZero(), JPH::Quat::sRotation(JPH::Vec3::sAxisZ(), -0.3f), JPH::EActivation::Activate);
            bodies.SetAngularVelocity(second->GetID(), JPH::Vec3(0, 0, 0.2f));
        }
        if (caseId == 7 && step == 241) {
            joint->SetLimitsSpringSettings(JPH::SpringSettings());
            joint->SetLimits(-0.2f, 0.2f);
            bodies.SetPositionAndRotation(second->GetID(), JPH::RVec3::sZero(), JPH::Quat::sRotation(JPH::Vec3::sAxisZ(), 0.4f), JPH::EActivation::Activate);
            bodies.SetAngularVelocity(second->GetID(), JPH::Vec3::sZero());
        }
        if (world.Update(delta, 1, &allocator, &jobs) != JPH::EPhysicsUpdateError::None) return 4;
        if (step % 15 == 0) {
            const auto point = bodies.GetPosition(second->GetID());
            const auto orientation = bodies.GetRotation(second->GetID());
            const auto firstAxis = bodies.GetRotation(first->GetID()) * JPH::Vec3::sAxisZ();
            const auto secondAxis = orientation * JPH::Vec3::sAxisZ();
            const auto firstSpeed = bodies.GetAngularVelocity(first->GetID());
            const auto secondSpeed = bodies.GetAngularVelocity(second->GetID());
            const float axisError = std::atan2(firstAxis.Cross(secondAxis).Length(), firstAxis.Dot(secondAxis));
            std::cout << "soft " << caseId << ' ' << step << ' ' << point.GetX() << ' ' << point.GetY()
                << ' ' << joint->GetCurrentAngle() + referenceAngle << ' ' << firstAxis.Dot(secondSpeed - firstSpeed)
                << ' ' << firstSpeed.GetZ() << ' ' << secondSpeed.GetZ()
                << ' ' << joint->GetTotalLambdaRotationLimits() / delta << ' ' << joint->GetTotalLambdaMotor() / delta
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
    for (int caseId = 0; caseId < 8 && result == 0; ++caseId) result = Physics3D::runSoftCase(caseId);
    JPH::UnregisterTypes();
    JPH::Factory::sInstance = nullptr;
    return result;
}
