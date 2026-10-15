#include <array>
#include <vector>
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
#include <Jolt/Physics/Body/Body.h>
#include <Jolt/Physics/Collision/BroadPhase/BroadPhaseLayerInterfaceTable.h>
#include <Jolt/Physics/Collision/BroadPhase/ObjectVsBroadPhaseLayerFilterTable.h>
#include <Jolt/Physics/Collision/ObjectLayerPairFilterTable.h>
#include <Jolt/Physics/Collision/GroupFilterTable.h>
#include <Jolt/Physics/Collision/Shape/SphereShape.h>
#include <Jolt/Physics/Collision/Shape/OffsetCenterOfMassShape.h>
#include <Jolt/Physics/Constraints/SwingTwistConstraint.h>
#include <Jolt/Physics/Ragdoll/Ragdoll.h>

namespace Physics3D {

// -----------------------------------------------------------------------------

JPH::Mat44 offset(int part) {
    if (part == 0) return JPH::Mat44::sRotationTranslation(JPH::Quat::sRotation(JPH::Vec3::sAxisY(), 0.3f), JPH::Vec3(0.2f, 0, 0));
    if (part == 1) return JPH::Mat44::sRotationTranslation(JPH::Quat::sRotation(JPH::Vec3::sAxisX(), 0.2f), JPH::Vec3(0, 0.2f, 0));
    return JPH::Mat44::sTranslation(JPH::Vec3(0, 0, 0.1f));
}

// -----------------------------------------------------------------------------

void writeVector(JPH::Vec3Arg value) {
    std::cout << ' ' << value.GetX() << ' ' << value.GetY() << ' ' << value.GetZ();
}

// -----------------------------------------------------------------------------

int runKinematic(int kind, int rate) {
    JPH::BroadPhaseLayerInterfaceTable broadPhase(1, 1);
    broadPhase.MapObjectToBroadPhaseLayer(0, JPH::BroadPhaseLayer(0));
    JPH::ObjectLayerPairFilterTable pairFilter(1);
    if (kind == 2) pairFilter.EnableCollision(0, 0);
    JPH::ObjectVsBroadPhaseLayerFilterTable phaseFilter(broadPhase, 1, pairFilter, 1);
    JPH::PhysicsSystem world;
    world.Init(16, 0, 16, 16, broadPhase, phaseFilter, pairFilter);
    world.SetGravity(JPH::Vec3::sZero());
    JPH::Ref<JPH::RagdollSettings> settings = new JPH::RagdollSettings;
    settings->mSkeleton = new JPH::Skeleton;
    JPH::RefConst<JPH::Shape> shape = new JPH::SphereShape(0.25f);
    if (kind != 2) shape = new JPH::OffsetCenterOfMassShape(shape, JPH::Vec3(0.1f, -0.2f, 0.3f));
    const int count = kind == 2 ? 1 : 3;
    std::array<JPH::Mat44, 3> targets;
    for (int i = 0; i < count; ++i) {
        settings->mSkeleton->AddJoint(i == 0 ? "root" : i == 1 ? "child" : "leaf", i - 1);
        const auto origin = kind == 2 ? JPH::Mat44::sIdentity() : JPH::Mat44::sTranslation(JPH::Vec3(static_cast<float>(i), 3, 0)) * offset(i);
        JPH::RagdollSettings::Part part;
        part.SetShape(shape);
        part.mPosition = JPH::RVec3(origin.GetTranslation());
        part.mRotation = origin.GetQuaternion();
        part.mMotionType = JPH::EMotionType::Dynamic;
        part.mObjectLayer = 0;
        part.mAllowSleeping = false;
        part.mLinearDamping = part.mAngularDamping = part.mFriction = 0;
        part.mOverrideMassProperties = JPH::EOverrideMassProperties::MassAndInertiaProvided;
        part.mMassPropertiesOverride.mMass = 2;
        part.mMassPropertiesOverride.mInertia = JPH::Mat44::sScale(JPH::Vec3::sReplicate(kind == 2 ? 0.05f : 0.2f));
        if (i > 0) {
            JPH::Ref<JPH::SwingTwistConstraintSettings> joint = new JPH::SwingTwistConstraintSettings;
            joint->mPosition1 = joint->mPosition2 = JPH::RVec3(static_cast<float>(i), 3, 0);
            joint->mPlaneHalfConeAngle = joint->mNormalHalfConeAngle = JPH::JPH_PI;
            joint->mTwistMinAngle = -JPH::JPH_PI;
            joint->mTwistMaxAngle = JPH::JPH_PI;
            part.mToParent = joint;
        }
        settings->mParts.push_back(part);
        const auto rotation = kind == 0 ? JPH::Quat::sRotation(JPH::Vec3::sAxisY(), 0.6f) : JPH::Quat::sIdentity();
        const auto shift = kind == 0 ? JPH::Vec3(1, 0, 0.5f) : JPH::Vec3(2, 0, 0);
        targets[i] = kind == 2 ? JPH::Mat44::sTranslation(JPH::Vec3(1, 0, 0))
            : JPH::Mat44::sRotationTranslation(rotation, JPH::Vec3(static_cast<float>(i), 3, 0) + shift) * offset(i);
    }
    settings->CalculateBodyIndexToConstraintIndex();
    settings->CalculateConstraintIndexToBodyIdxPair();
    JPH::Ref<JPH::Ragdoll> ragdoll = settings->CreateRagdoll(1, 0, &world);
    if (!ragdoll) return 3;
    ragdoll->AddToPhysicsSystem(JPH::EActivation::Activate);
    auto& bodies = world.GetBodyInterface();
    std::vector<JPH::BodyID> members;
    for (int i = 0; i < count; ++i) {
        members.push_back(ragdoll->GetBodyID(i));
        bodies.SetMotionType(members.back(), JPH::EMotionType::Kinematic, JPH::EActivation::Activate);
    }
    JPH::BodyID external;
    if (kind == 2) {
        JPH::BodyCreationSettings body = settings->mParts[0];
        body.mPosition = JPH::RVec3(0.75f, 0, 0);
        external = bodies.CreateAndAddBody(body, JPH::EActivation::Activate);
        members.push_back(external);
    }
    ragdoll->DriveToPoseUsingKinematics(JPH::RVec3::sZero(), targets.data(), 1);
    JPH::TempAllocatorImpl allocator(1024 * 1024);
    JPH::JobSystemSingleThreaded jobs(JPH::cMaxPhysicsJobs);
    int stage = 0;
    for (int step = 0; step <= rate * 5 / 4; ++step) {
        if (step == rate && kind != 1) {
            for (int i = 0; i < count; ++i) {
                bodies.SetPositionAndRotation(members[i], JPH::RVec3(targets[i].GetTranslation()), targets[i].GetQuaternion(), JPH::EActivation::Activate);
                bodies.SetLinearAndAngularVelocity(members[i], JPH::Vec3::sZero(), JPH::Vec3::sZero());
            }
        }
        if (step == 0 || step == rate / 4 || step == rate / 2 || step == rate * 3 / 4 || step == rate * 5 / 4) {
            for (int i = 0; i < static_cast<int>(members.size()); ++i) {
                const auto q = bodies.GetRotation(members[i]);
                std::cout << "kinematic " << kind << ' ' << rate << ' ' << stage << ' ' << i;
                writeVector(JPH::Vec3(bodies.GetCenterOfMassPosition(members[i])));
                std::cout << ' ' << q.GetX() << ' ' << q.GetY() << ' ' << q.GetZ() << ' ' << q.GetW();
                writeVector(bodies.GetLinearVelocity(members[i]));
                writeVector(bodies.GetAngularVelocity(members[i]));
                std::cout << '\n';
            }
            ++stage;
        }
        if (kind == 1 && step == rate / 4) {
            for (int i = 0; i < count; ++i) bodies.SetMotionType(members[i], JPH::EMotionType::Dynamic, JPH::EActivation::Activate);
            ragdoll->ResetWarmStart();
        }
        if (step < rate * 5 / 4 && world.Update(1.0f / rate, 1, &allocator, &jobs) != JPH::EPhysicsUpdateError::None) return 5;
    }
    ragdoll->RemoveFromPhysicsSystem();
    ragdoll = nullptr;
    if (kind == 2) { bodies.RemoveBody(external); bodies.DestroyBody(external); }
    return 0;
}

// -----------------------------------------------------------------------------

} // namespace Physics3D

int main() {
#ifdef JPH_ENABLE_ASSERTS
    JPH::AssertFailed = [](const char* expression, const char*, const char*, JPH::uint) {
        std::cerr << "Jolt assertion: " << expression << '\n';
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
    for (int kind : { 0, 1, 2 }) for (int rate : { 60, 120 }) {
        if (result == 0) result = Physics3D::runKinematic(kind, rate);
    }
    JPH::UnregisterTypes();
    JPH::Factory::sInstance = nullptr;
    return result;
}
