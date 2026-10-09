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
#include <Jolt/Physics/Constraints/SliderConstraint.h>
#include <Jolt/Physics/Constraints/HingeConstraint.h>

namespace Physics3D {

// -----------------------------------------------------------------------------

int runLoaded(int kind, int massId, int rate, int direction) {
    const float delta = 1.0f / static_cast<float>(rate);
    const float sign = static_cast<float>(direction);
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
    auto physicsSettings = world.GetPhysicsSettings();
    physicsSettings.mNumVelocitySteps = 24;
    physicsSettings.mNumPositionSteps = 8;
    world.SetPhysicsSettings(physicsSettings);
    world.SetGravity(JPH::Vec3(0, -9.81f, 0));
    JPH::RefConst<JPH::SphereShape> sphere = new JPH::SphereShape(0.25f);
    JPH::BodyCreationSettings pivotSettings(sphere, JPH::RVec3::sZero(), JPH::Quat::sIdentity(), JPH::EMotionType::Static, 0);
    JPH::BodyCreationSettings firstSettings(sphere, JPH::RVec3::sZero(), JPH::Quat::sIdentity(), JPH::EMotionType::Dynamic, 0);
    firstSettings.mAllowSleeping = false;
    firstSettings.mLinearDamping = firstSettings.mAngularDamping = 0;
    firstSettings.mOverrideMassProperties = JPH::EOverrideMassProperties::MassAndInertiaProvided;
    firstSettings.mMassPropertiesOverride.mMass = 2;
    firstSettings.mMassPropertiesOverride.mInertia = JPH::Mat44::sScale(JPH::Vec3::sReplicate(0.4f));
    JPH::BodyCreationSettings bodySettings(sphere, JPH::RVec3(sign, 0, 0), JPH::Quat::sIdentity(), JPH::EMotionType::Dynamic, 1);
    bodySettings.mAllowSleeping = false;
    bodySettings.mLinearDamping = bodySettings.mAngularDamping = 0;
    bodySettings.mFriction = bodySettings.mRestitution = 0;
    bodySettings.mOverrideMassProperties = JPH::EOverrideMassProperties::MassAndInertiaProvided;
    bodySettings.mMassPropertiesOverride.mMass = mass;
    bodySettings.mMassPropertiesOverride.mInertia = JPH::Mat44::sScale(JPH::Vec3::sReplicate(0.2f));
    auto& bodies = world.GetBodyInterface();
    auto* pivot = bodies.CreateBody(pivotSettings);
    auto* first = bodies.CreateBody(firstSettings);
    auto* body = bodies.CreateBody(bodySettings);
    if (!pivot || !first || !body) return 3;
    bodies.AddBody(pivot->GetID(), JPH::EActivation::DontActivate);
    bodies.AddBody(first->GetID(), JPH::EActivation::Activate);
    bodies.AddBody(body->GetID(), JPH::EActivation::Activate);
    JPH::Body* wall = nullptr;
    if (kind == 1) {
        JPH::RefConst<JPH::PlaneShape> plane = new JPH::PlaneShape(JPH::Plane(JPH::Vec3(-sign, 0, 0), 1.4f));
        JPH::BodyCreationSettings wallSettings(plane, JPH::RVec3::sZero(), JPH::Quat::sIdentity(), JPH::EMotionType::Static, 2);
        wallSettings.mFriction = wallSettings.mRestitution = 0;
        wall = bodies.CreateBody(wallSettings);
        if (!wall) return 3;
        bodies.AddBody(wall->GetID(), JPH::EActivation::DontActivate);
    }
    JPH::HingeConstraintSettings hingeSettings;
    hingeSettings.mSpace = JPH::EConstraintSpace::LocalToBodyCOM;
    hingeSettings.mPoint1 = hingeSettings.mPoint2 = JPH::RVec3::sZero();
    hingeSettings.mHingeAxis1 = hingeSettings.mHingeAxis2 = JPH::Vec3::sAxisZ();
    hingeSettings.mNormalAxis1 = hingeSettings.mNormalAxis2 = JPH::Vec3::sAxisX();
    hingeSettings.mMotorSettings.mMinTorqueLimit = -30;
    hingeSettings.mMotorSettings.mMaxTorqueLimit = 30;
    JPH::Ref<JPH::HingeConstraint> hinge = new JPH::HingeConstraint(*pivot, *first, hingeSettings);
    hinge->SetTargetAngularVelocity(0); hinge->SetMotorState(JPH::EMotorState::Velocity);
    world.AddConstraint(hinge.GetPtr());
    JPH::SliderConstraintSettings settings;
    settings.mSpace = JPH::EConstraintSpace::LocalToBodyCOM;
    settings.mAutoDetectPoint = false;
    settings.mPoint1 = settings.mPoint2 = JPH::RVec3::sZero();
    settings.mSliderAxis1 = settings.mSliderAxis2 = JPH::Vec3::sAxisX();
    settings.mNormalAxis1 = settings.mNormalAxis2 = JPH::Vec3::sAxisY();
    settings.mMotorSettings.mMinForceLimit = -2;
    settings.mMotorSettings.mMaxForceLimit = 2;
    JPH::Ref<JPH::SliderConstraint> joint = new JPH::SliderConstraint(*first, *body, settings);
    joint->SetTargetVelocity(0.6f * sign); joint->SetMotorState(JPH::EMotorState::Velocity);
    world.AddConstraint(joint.GetPtr());
    JPH::TempAllocatorImpl allocator(1024 * 1024);
    JPH::JobSystemSingleThreaded jobs(JPH::cMaxPhysicsJobs);
    for (int step = 1; step <= rate * 2; ++step) {
        if (step == rate * 2 / 3 + 1) joint->SetTargetVelocity(-0.6f * sign);
        if (step == rate * 4 / 3 + 1) joint->SetTargetVelocity(0);
        const auto beforeVelocity = bodies.GetLinearVelocity(body->GetID());
        const auto beforeRailVelocity = bodies.GetLinearVelocity(first->GetID());
        const float beforeSpin = bodies.GetAngularVelocity(body->GetID()).GetZ();
        const auto beforeRotation = bodies.GetRotation(first->GetID());
        if (world.Update(delta, 1, &allocator, &jobs) != JPH::EPhysicsUpdateError::None) return 4;
        const auto afterRotation = bodies.GetRotation(first->GetID());
        const auto axis = afterRotation * JPH::Vec3::sAxisX();
        const auto position = bodies.GetPosition(body->GetID());
        const auto velocity = bodies.GetLinearVelocity(body->GetID());
        const auto offset = JPH::Vec3(position - bodies.GetPosition(first->GetID()));
        const auto railVelocity = bodies.GetLinearVelocity(first->GetID());
        const auto railPosition = bodies.GetPosition(first->GetID());
        const auto railAngular = bodies.GetAngularVelocity(first->GetID());
        const auto relative = velocity - railVelocity - railAngular.Cross(offset);
        const auto lambda = JPH::Vec3(joint->GetTotalLambdaPositionLimits() + joint->GetTotalLambdaMotor(), joint->GetTotalLambdaPosition()[0], joint->GetTotalLambdaPosition()[1]);
        const auto force = beforeRotation * lambda / delta;
        const auto hingeForce = hinge->GetTotalLambdaPosition() / delta;
        const auto difference = bodies.GetRotation(body->GetID()) * afterRotation.Conjugated();
        const float angleError = 2 * std::atan2(JPH::Vec3(difference.GetX(), difference.GetY(), difference.GetZ()).Length(), std::abs(difference.GetW()));
        const auto inferred = mass * (velocity - beforeVelocity) - force * delta + JPH::Vec3(0, mass * 9.81f * delta, 0);
        const int contact = wall && world.WereBodiesInContact(wall->GetID(), body->GetID()) ? 1 : 0;
        std::cout << "loadedrail " << kind << ' ' << massId << ' ' << rate << ' ' << direction << ' ' << step
            << ' ' << joint->GetCurrentPosition() << ' ' << relative.Dot(axis)
            << ' ' << railPosition.GetX() << ' ' << railPosition.GetY()
            << ' ' << railVelocity.GetX() << ' ' << railVelocity.GetY() << ' ' << railAngular.GetZ()
            << ' ' << position.GetX() << ' ' << position.GetY() << ' ' << velocity.GetX() << ' ' << velocity.GetY()
            << ' ' << bodies.GetAngularVelocity(body->GetID()).GetZ()
            << ' ' << hinge->GetTotalLambdaMotor() / delta << ' ' << hingeForce.GetX() << ' ' << hingeForce.GetY()
            << ' ' << force.GetX() << ' ' << force.GetY() << ' ' << joint->GetTotalLambdaMotor() / delta
            << ' ' << joint->GetTotalLambdaRotation().GetZ() / delta
            << ' ' << JPH::Vec3(railPosition).Length()
            << ' ' << std::atan2((afterRotation * JPH::Vec3::sAxisZ()).Cross(JPH::Vec3::sAxisZ()).Length(), (afterRotation * JPH::Vec3::sAxisZ()).Dot(JPH::Vec3::sAxisZ()))
            << ' ' << (offset - axis * offset.Dot(axis)).Length() << ' ' << angleError << ' ' << axis.GetX() << ' ' << axis.GetY()
            << ' ' << beforeVelocity.GetX() << ' ' << beforeVelocity.GetY()
            << ' ' << beforeRailVelocity.GetX() << ' ' << beforeRailVelocity.GetY() << ' ' << beforeSpin
            << ' ' << inferred.GetX() << ' ' << inferred.GetY() << ' ' << contact
            << ' ' << std::max(0.0f, sign * static_cast<float>(position.GetX()) + 0.25f - 1.4f)
            << ' ' << std::atan2(axis.GetY(), axis.GetX()) << " 0\n";
    }
    if (wall) { const auto id = wall->GetID(); bodies.RemoveBody(id); bodies.DestroyBody(id); }
    world.RemoveConstraint(joint.GetPtr()); world.RemoveConstraint(hinge.GetPtr());
    const auto pivotId = pivot->GetID();
    const auto firstId = first->GetID(); const auto bodyId = body->GetID();
    bodies.RemoveBody(pivotId); bodies.RemoveBody(firstId); bodies.RemoveBody(bodyId);
    bodies.DestroyBody(pivotId); bodies.DestroyBody(firstId); bodies.DestroyBody(bodyId);
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
        for (int massId : {0, 1}) {
            for (int rate : {60, 120}) {
                for (int direction : {1, -1}) {
                    if (result == 0) result = Physics3D::runLoaded(kind, massId, rate, direction);
                }
            }
        }
    }
    JPH::UnregisterTypes();
    JPH::Factory::sInstance = nullptr;
    return result;
}
