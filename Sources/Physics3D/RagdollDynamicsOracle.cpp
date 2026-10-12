#include <array>
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
#include <Jolt/Physics/Collision/Shape/BoxShape.h>
#include <Jolt/Physics/Constraints/SwingTwistConstraint.h>
#include <Jolt/Physics/Ragdoll/Ragdoll.h>

namespace Physics3D {

// -----------------------------------------------------------------------------

void writeVector(JPH::Vec3Arg value) {
    std::cout << ' ' << value.GetX() << ' ' << value.GetY() << ' ' << value.GetZ();
}

int runDynamics(int caseId, int rate, int side) {
    JPH::BroadPhaseLayerInterfaceTable broadPhase(1, 1);
    broadPhase.MapObjectToBroadPhaseLayer(0, JPH::BroadPhaseLayer(0));
    JPH::ObjectLayerPairFilterTable pairFilter(1);
    pairFilter.EnableCollision(0, 0);
    JPH::ObjectVsBroadPhaseLayerFilterTable phaseFilter(broadPhase, 1, pairFilter, 1);
    JPH::PhysicsSystem world;
    world.Init(16, 0, 16, 16, broadPhase, phaseFilter, pairFilter);
    world.SetGravity(caseId == 0 ? JPH::Vec3::sZero() : JPH::Vec3(0, -9.81f, 0));
    JPH::Ref<JPH::RagdollSettings> settings = new JPH::RagdollSettings;
    settings->mSkeleton = new JPH::Skeleton;
    settings->mSkeleton->AddJoint("root", -1);
    settings->mSkeleton->AddJoint("child", 0);
    settings->mSkeleton->AddJoint("leaf", 1);
    JPH::RefConst<JPH::SphereShape> shape = new JPH::SphereShape(0.25f);
    JPH::Ref<JPH::GroupFilterTable> groups = new JPH::GroupFilterTable(3);
    for (int i = 0; i < 3; ++i) for (int j = i + 1; j < 3; ++j) groups->DisableCollision(i, j);
    for (int i = 0; i < 3; ++i) {
        JPH::RagdollSettings::Part part;
        part.SetShape(shape);
        part.mPosition = JPH::RVec3(static_cast<float>(i), 3, 0);
        part.mMotionType = JPH::EMotionType::Dynamic;
        part.mObjectLayer = 0;
        part.mAllowSleeping = false;
        part.mLinearDamping = part.mAngularDamping = part.mFriction = 0;
        part.mOverrideMassProperties = JPH::EOverrideMassProperties::MassAndInertiaProvided;
        part.mMassPropertiesOverride.mMass = 2;
        part.mMassPropertiesOverride.mInertia = JPH::Mat44::sScale(JPH::Vec3::sReplicate(0.2f));
        part.mCollisionGroup = JPH::CollisionGroup(groups, 1, i);
        if (i > 0) {
            JPH::Ref<JPH::SwingTwistConstraintSettings> joint = new JPH::SwingTwistConstraintSettings;
            joint->mPosition1 = joint->mPosition2 = JPH::RVec3(i - 0.5f, 3, 0);
            joint->mPlaneHalfConeAngle = joint->mNormalHalfConeAngle = JPH::JPH_PI;
            joint->mTwistMinAngle = -JPH::JPH_PI;
            joint->mTwistMaxAngle = JPH::JPH_PI;
            part.mToParent = joint;
        }
        settings->mParts.push_back(part);
    }
    settings->CalculateBodyIndexToConstraintIndex();
    settings->CalculateConstraintIndexToBodyIdxPair();
    JPH::Ref<JPH::Ragdoll> ragdoll = settings->CreateRagdoll(1, 0, &world);
    if (!ragdoll) return 3;
    ragdoll->AddToPhysicsSystem(JPH::EActivation::Activate);
    auto& bodies = world.GetBodyInterface();
    JPH::BodyID floor;
    if (caseId == 0) {
        bodies.AddImpulse(ragdoll->GetBodyID(2), JPH::Vec3(0, 0, 3.0f * side), JPH::RVec3(2, 3.1f, 0));
    } else {
        JPH::RefConst<JPH::BoxShape> floorShape = new JPH::BoxShape(JPH::Vec3(10, 0.5f, 10));
        JPH::BodyCreationSettings floorSettings(floorShape, JPH::RVec3(0, -0.5f, 0), JPH::Quat::sIdentity(), JPH::EMotionType::Static, 0);
        floorSettings.mFriction = 0;
        auto* floorBody = bodies.CreateBody(floorSettings);
        if (!floorBody) return 4;
        floor = floorBody->GetID();
        bodies.AddBody(floor, JPH::EActivation::DontActivate);
    }
    JPH::TempAllocatorImpl allocator(1024 * 1024);
    JPH::JobSystemSingleThreaded jobs(JPH::cMaxPhysicsJobs);
    const int steps = caseId == 0 ? rate / 2 : rate * 2;
    for (int step = 0; step <= steps; ++step) {
        for (int i = 0; i < 3; ++i) {
            float error = 0;
            if (i > 0) {
                const auto first = bodies.GetPosition(ragdoll->GetBodyID(i - 1)) + bodies.GetRotation(ragdoll->GetBodyID(i - 1)) * JPH::Vec3(0.5f, 0, 0);
                const auto second = bodies.GetPosition(ragdoll->GetBodyID(i)) + bodies.GetRotation(ragdoll->GetBodyID(i)) * JPH::Vec3(-0.5f, 0, 0);
                error = static_cast<float>((first - second).Length());
            }
            std::cout << "dynamic " << caseId << ' ' << rate << ' ' << side << ' ' << step << ' ' << i;
            writeVector(JPH::Vec3(bodies.GetCenterOfMassPosition(ragdoll->GetBodyID(i))));
            writeVector(bodies.GetLinearVelocity(ragdoll->GetBodyID(i)));
            writeVector(bodies.GetAngularVelocity(ragdoll->GetBodyID(i)));
            std::cout << ' ' << error << '\n';
        }
        if (step < steps && world.Update(1.0f / rate, 1, &allocator, &jobs) != JPH::EPhysicsUpdateError::None) return 5;
    }
    ragdoll->RemoveFromPhysicsSystem();
    ragdoll = nullptr;
    if (caseId == 1) { bodies.RemoveBody(floor); bodies.DestroyBody(floor); }
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
    for (int caseId : { 0, 1 }) for (int rate : { 60, 120 }) for (int side : { -1, 1 }) {
        if (result == 0) result = Physics3D::runDynamics(caseId, rate, side);
    }
    JPH::UnregisterTypes();
    JPH::Factory::sInstance = nullptr;
    return result;
}
