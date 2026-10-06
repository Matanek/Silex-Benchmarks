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

int runFrictionCase(int caseId) {
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
    world.SetGravity(caseId == 7 ? JPH::Vec3(0, -9.81f, 0) : JPH::Vec3::sZero());
    JPH::RefConst<JPH::SphereShape> sphere = new JPH::SphereShape(0.5f);
    auto anchor = JPH::Vec3::sZero();
    auto position = JPH::RVec3::sZero();
    if (caseId == 2 || caseId == 7) { anchor = JPH::Vec3(0, 1, 0); position = JPH::RVec3(0, -1, 0); }
    auto rotation = JPH::Quat::sIdentity();
    if (caseId == 7) { rotation = JPH::Quat::sRotation(JPH::Vec3::sAxisZ(), 0.3f); position = JPH::RVec3(rotation * JPH::Vec3(0, -1, 0)); }
    JPH::BodyCreationSettings firstSettings(sphere, JPH::RVec3::sZero(), JPH::Quat::sIdentity(),
        caseId == 3 ? JPH::EMotionType::Dynamic : JPH::EMotionType::Static, 0);
    firstSettings.mAllowSleeping = false;
    firstSettings.mLinearDamping = firstSettings.mAngularDamping = 0;
    firstSettings.mOverrideMassProperties = JPH::EOverrideMassProperties::CalculateInertia;
    firstSettings.mMassPropertiesOverride.mMass = 1;
    JPH::BodyCreationSettings secondSettings(sphere, position,
        rotation, JPH::EMotionType::Dynamic, 0);
    secondSettings.mAllowSleeping = false;
    secondSettings.mLinearDamping = secondSettings.mAngularDamping = 0;
    secondSettings.mOverrideMassProperties = JPH::EOverrideMassProperties::MassAndInertiaProvided;
    secondSettings.mMassPropertiesOverride.mMass = 1;
    const float inertia = caseId == 3 ? 0.4f : 0.1f;
    secondSettings.mMassPropertiesOverride.mInertia = JPH::Mat44::sScale(JPH::Vec3::sReplicate(inertia));
    auto& bodies = world.GetBodyInterface();
    auto* first = bodies.CreateBody(firstSettings);
    auto* second = bodies.CreateBody(secondSettings);
    if (!first || !second) return 3;
    bodies.AddBody(first->GetID(), caseId == 3 ? JPH::EActivation::Activate : JPH::EActivation::DontActivate);
    bodies.AddBody(second->GetID(), JPH::EActivation::Activate);
    float speed = caseId == 1 ? -1.0f : 1.0f;
    float friction = 0.1f;
    if (caseId == 2) { speed = 0.8f; friction = 0.3f; }
    if (caseId == 3) friction = 0.02f;
    if (caseId == 4) friction = 0.05f;
    if (caseId == 5) friction = 0.4f;
    if (caseId == 6) friction = 1.0f;
    if (caseId == 7) { speed = 0.0f; friction = 4.0f; }
    bodies.SetAngularVelocity(second->GetID(), JPH::Vec3(0, 0, speed));
    if (caseId == 2) bodies.SetLinearVelocity(second->GetID(), JPH::Vec3(speed, 0, 0));
    JPH::HingeConstraintSettings settings;
    settings.mSpace = JPH::EConstraintSpace::LocalToBodyCOM;
    settings.mPoint1 = JPH::RVec3::sZero();
    settings.mPoint2 = JPH::RVec3(anchor);
    settings.mHingeAxis1 = settings.mHingeAxis2 = JPH::Vec3::sAxisZ();
    settings.mNormalAxis1 = settings.mNormalAxis2 = JPH::Vec3::sAxisX();
    settings.mMaxFrictionTorque = friction;
    settings.mMotorSettings.SetTorqueLimit(caseId == 6 ? 0.0f : 0.2f);
    settings.mMotorSettings.mSpringSettings = JPH::SpringSettings(JPH::ESpringMode::StiffnessAndDamping, 1.6f, 0.8f);
    JPH::Ref<JPH::HingeConstraint> joint = new JPH::HingeConstraint(*first, *second, settings);
    if (caseId == 5 || caseId == 6) { joint->SetTargetAngularVelocity(caseId == 5 ? 0.5f : 0.0f); joint->SetMotorState(JPH::EMotorState::Velocity); }
    world.AddConstraint(joint.GetPtr());
    JPH::TempAllocatorImpl allocator(1024 * 1024);
    JPH::JobSystemSingleThreaded jobs(JPH::cMaxPhysicsJobs);
    constexpr float delta = 1.0f / 60.0f;
    for (int step = 1; step <= 360; ++step) {
        if (caseId == 4 && step == 61) joint->SetMaxFrictionTorque(0.2f);
        if (caseId == 4 && step == 181) { joint->SetMaxFrictionTorque(0.0f); bodies.SetAngularVelocity(second->GetID(), JPH::Vec3(0, 0, -1)); }
        if (caseId == 4 && step == 241) joint->SetMaxFrictionTorque(0.1f);
        if (caseId == 5 && step == 121) { joint->GetMotorSettings().SetTorqueLimit(1.0f); joint->SetTargetAngle(-0.5f); joint->SetMotorState(JPH::EMotorState::Position); }
        if (caseId == 5 && step == 301) joint->SetMotorState(JPH::EMotorState::Off);
        if (caseId == 6 && step == 121) joint->SetMotorState(JPH::EMotorState::Off);
        if (caseId == 6 && step == 181) { joint->SetMotorState(JPH::EMotorState::Velocity); bodies.SetAngularVelocity(second->GetID(), JPH::Vec3(0, 0, -1)); }
        if (caseId == 6 && step == 241) { joint->SetTargetAngle(0.0f); joint->SetMotorState(JPH::EMotorState::Position); }
        if (caseId == 7 && step == 181) joint->SetMaxFrictionTorque(1.0f);
        if (world.Update(delta, 1, &allocator, &jobs) != JPH::EPhysicsUpdateError::None) return 4;
        if (step % 15 == 0) {
            const auto point = bodies.GetPosition(second->GetID());
            const auto orientation = bodies.GetRotation(second->GetID());
            const auto firstAxis = bodies.GetRotation(first->GetID()) * JPH::Vec3::sAxisZ();
            const auto secondAxis = orientation * JPH::Vec3::sAxisZ();
            const auto firstSpeed = bodies.GetAngularVelocity(first->GetID());
            const auto secondSpeed = bodies.GetAngularVelocity(second->GetID());
            const float axisError = std::atan2(firstAxis.Cross(secondAxis).Length(), firstAxis.Dot(secondAxis));
            std::cout << "friction " << caseId << ' ' << step << ' ' << point.GetX() << ' ' << point.GetY()
                << ' ' << joint->GetCurrentAngle() << ' ' << firstAxis.Dot(secondSpeed - firstSpeed)
                << ' ' << firstSpeed.GetZ() << ' ' << secondSpeed.GetZ()
                << ' ' << (joint->GetMotorState() == JPH::EMotorState::Off ? joint->GetTotalLambdaMotor() / delta : 0.0f)
                << ' ' << (joint->GetMotorState() != JPH::EMotorState::Off ? joint->GetTotalLambdaMotor() / delta : 0.0f)
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
    for (int caseId = 0; caseId < 8 && result == 0; ++caseId) result = Physics3D::runFrictionCase(caseId);
    JPH::UnregisterTypes();
    JPH::Factory::sInstance = nullptr;
    return result;
}
