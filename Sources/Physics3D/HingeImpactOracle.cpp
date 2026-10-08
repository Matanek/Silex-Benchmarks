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

int runImpactCase(int recipe, int rate, float sign) {
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
    world.SetGravity(JPH::Vec3::sZero());
    float angle = 0;
    float speed = sign;
    if (recipe == 1) angle = sign * 0.283f;
    if (recipe == 2 || recipe == 3) angle = sign * 0.3f;
    if (recipe == 3) speed = -sign;
    if (recipe >= 5) speed = 0;
    JPH::RefConst<JPH::SphereShape> sphere = new JPH::SphereShape(0.5f);
    JPH::BodyCreationSettings firstSettings(sphere, JPH::RVec3::sZero(), JPH::Quat::sIdentity(),
        JPH::EMotionType::Static, 0);
    JPH::BodyCreationSettings secondSettings(sphere, JPH::RVec3::sZero(),
        JPH::Quat::sRotation(JPH::Vec3::sAxisZ(), angle), JPH::EMotionType::Dynamic, 0);
    secondSettings.mAllowSleeping = false;
    secondSettings.mLinearDamping = secondSettings.mAngularDamping = 0;
    secondSettings.mAngularVelocity = JPH::Vec3(0, 0, speed);
    secondSettings.mOverrideMassProperties = JPH::EOverrideMassProperties::MassAndInertiaProvided;
    secondSettings.mMassPropertiesOverride.mMass = 1;
    secondSettings.mMassPropertiesOverride.mInertia = JPH::Mat44::sScale(JPH::Vec3::sReplicate(0.1f));
    auto& bodies = world.GetBodyInterface();
    auto* first = bodies.CreateBody(firstSettings);
    auto* second = bodies.CreateBody(secondSettings);
    if (!first || !second) return 3;
    bodies.AddBody(first->GetID(), JPH::EActivation::DontActivate);
    bodies.AddBody(second->GetID(), JPH::EActivation::Activate);
    JPH::HingeConstraintSettings settings;
    settings.mSpace = JPH::EConstraintSpace::LocalToBodyCOM;
    settings.mPoint1 = settings.mPoint2 = JPH::RVec3::sZero();
    settings.mHingeAxis1 = settings.mHingeAxis2 = JPH::Vec3::sAxisZ();
    settings.mNormalAxis1 = settings.mNormalAxis2 = JPH::Vec3::sAxisX();
    if (recipe != 4 && recipe != 5) { settings.mLimitsMin = -0.3f; settings.mLimitsMax = 0.3f; }
    if (recipe >= 5) {
        settings.mMotorSettings.mMinTorqueLimit = -10;
        settings.mMotorSettings.mMaxTorqueLimit = 10;
        settings.mMotorSettings.mSpringSettings = JPH::SpringSettings(JPH::ESpringMode::StiffnessAndDamping, 1.6f, 0.08f);
    }
    JPH::Ref<JPH::HingeConstraint> joint = new JPH::HingeConstraint(*first, *second, settings);
    if (recipe >= 5) { joint->SetTargetAngle(sign * 0.8f); joint->SetMotorState(JPH::EMotorState::Position); }
    world.AddConstraint(joint.GetPtr());
    JPH::TempAllocatorImpl allocator(1024 * 1024);
    JPH::JobSystemSingleThreaded jobs(JPH::cMaxPhysicsJobs);
    const float delta = 1.0f / static_cast<float>(rate);
    const auto geometricAngle = [&]() {
        const auto normal = bodies.GetRotation(second->GetID()) * JPH::Vec3::sAxisX();
        return std::atan2(normal.GetY(), normal.GetX());
    };
    const int duration = recipe >= 5 ? 6 : 1;
    for (int step = 1; step <= rate * duration; ++step) {
        if (recipe >= 5 && step == rate * 3 + 1) joint->SetTargetAngle(-sign * 0.8f);
        const float beforeAngle = geometricAngle();
        const float beforeSpeed = bodies.GetAngularVelocity(second->GetID()).GetZ();
        if (world.Update(delta, 1, &allocator, &jobs) != JPH::EPhysicsUpdateError::None) return 4;
        std::cout << "impact " << recipe << ' ' << rate << ' ' << sign << ' ' << step
            << ' ' << beforeAngle << ' ' << beforeSpeed << ' ' << geometricAngle()
            << ' ' << bodies.GetAngularVelocity(second->GetID()).GetZ()
            << ' ' << joint->GetTotalLambdaRotationLimits() << ' ' << joint->GetTotalLambdaMotor()
            << ' ' << (bodies.GetPosition(second->GetID()) - bodies.GetPosition(first->GetID())).Length()
            << ' ' << std::atan2((bodies.GetRotation(second->GetID()) * JPH::Vec3::sAxisZ()).Cross(JPH::Vec3::sAxisZ()).Length(), (bodies.GetRotation(second->GetID()) * JPH::Vec3::sAxisZ()).Dot(JPH::Vec3::sAxisZ())) << '\n';
    }
    world.RemoveConstraint(joint.GetPtr());
    const auto firstId = first->GetID();
    const auto secondId = second->GetID();
    bodies.RemoveBody(firstId); bodies.RemoveBody(secondId);
    bodies.DestroyBody(firstId); bodies.DestroyBody(secondId);
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
    for (int recipe = 0; recipe < 7 && result == 0; ++recipe) {
        for (int rate : {60, 120}) {
            for (float sign : {-1.0f, 1.0f}) {
                if (result == 0) result = Physics3D::runImpactCase(recipe, rate, sign);
            }
        }
    }
    JPH::UnregisterTypes();
    JPH::Factory::sInstance = nullptr;
    return result;
}
