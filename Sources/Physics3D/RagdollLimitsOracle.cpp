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
#include <Jolt/Physics/Body/Body.h>
#include <Jolt/Physics/Collision/BroadPhase/BroadPhaseLayerInterfaceTable.h>
#include <Jolt/Physics/Collision/BroadPhase/ObjectVsBroadPhaseLayerFilterTable.h>
#include <Jolt/Physics/Collision/ObjectLayerPairFilterTable.h>
#include <Jolt/Physics/Collision/GroupFilterTable.h>
#include <Jolt/Physics/Collision/Shape/SphereShape.h>
#include <Jolt/Physics/Constraints/SwingTwistConstraint.h>
#include <Jolt/Physics/Ragdoll/Ragdoll.h>

namespace Physics3D {

// -----------------------------------------------------------------------------

void writeVector(JPH::Vec3Arg value) {
    std::cout << ' ' << value.GetX() << ' ' << value.GetY() << ' ' << value.GetZ();
}

int runLimits(int rate, int side, int frame) {
    JPH::BroadPhaseLayerInterfaceTable broadPhase(1, 1);
    broadPhase.MapObjectToBroadPhaseLayer(0, JPH::BroadPhaseLayer(0));
    JPH::ObjectLayerPairFilterTable pairFilter(1);
    pairFilter.EnableCollision(0, 0);
    JPH::ObjectVsBroadPhaseLayerFilterTable phaseFilter(broadPhase, 1, pairFilter, 1);
    JPH::PhysicsSystem world;
    world.Init(16, 0, 16, 16, broadPhase, phaseFilter, pairFilter);
    world.SetGravity(JPH::Vec3::sZero());
    auto physicsSettings = world.GetPhysicsSettings();
    physicsSettings.mNumPositionSteps = 8;
    world.SetPhysicsSettings(physicsSettings);
    const auto base = frame == 0 ? JPH::Quat::sIdentity()
        : JPH::Quat::sRotation(JPH::Vec3(1, 2, -1).Normalized(), 0.6f);
    const auto axis = base * JPH::Vec3::sAxisX();
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
        part.mPosition = JPH::RVec3(0, 3, 0) + base * JPH::Vec3(static_cast<float>(i), 0, 0);
        part.mRotation = base;
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
            joint->mPosition1 = joint->mPosition2 = JPH::RVec3(0, 3, 0) + base * JPH::Vec3(i - 0.5f, 0, 0);
            joint->mTwistAxis1 = joint->mTwistAxis2 = axis;
            joint->mPlaneAxis1 = joint->mPlaneAxis2 = base * JPH::Vec3::sAxisZ();
            joint->mPlaneHalfConeAngle = joint->mNormalHalfConeAngle = 0;
            joint->mTwistMinAngle = -0.2f;
            joint->mTwistMaxAngle = 0.35f;
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
    JPH::TempAllocatorImpl allocator(1024 * 1024);
    JPH::JobSystemSingleThreaded jobs(JPH::cMaxPhysicsJobs);
    const auto observe = [&](const char* label, int step) {
        for (int i = 0; i < 3; ++i) {
            float error = 0;
            float twistAngle = 0;
            float swingY = 0;
            float swingZ = 0;
            if (i > 0) {
                const auto first = bodies.GetPosition(ragdoll->GetBodyID(i - 1)) + bodies.GetRotation(ragdoll->GetBodyID(i - 1)) * JPH::Vec3(0.5f, 0, 0);
                const auto second = bodies.GetPosition(ragdoll->GetBodyID(i)) + bodies.GetRotation(ragdoll->GetBodyID(i)) * JPH::Vec3(-0.5f, 0, 0);
                error = static_cast<float>((first - second).Length());
                const auto* joint = static_cast<const JPH::SwingTwistConstraint*>(ragdoll->GetConstraint(i - 1));
                JPH::Quat swing, twist;
                joint->GetRotationInConstraintSpace().GetSwingTwist(swing, twist);
                if (swing.GetW() < 0) swing = -swing;
                if (twist.GetW() < 0) twist = -twist;
                twistAngle = 2 * std::atan2(twist.GetX(), twist.GetW());
                swingY = 2 * std::atan2(swing.GetY(), swing.GetW());
                swingZ = 2 * std::atan2(swing.GetZ(), swing.GetW());
            }
            std::cout << label << rate << ' ' << side << ' ' << frame << ' ' << step << ' ' << i;
            writeVector(JPH::Vec3(bodies.GetPosition(ragdoll->GetBodyID(i))));
            const auto q = bodies.GetRotation(ragdoll->GetBodyID(i));
            std::cout << ' ' << q.GetX() << ' ' << q.GetY() << ' ' << q.GetZ() << ' ' << q.GetW();
            writeVector(bodies.GetLinearVelocity(ragdoll->GetBodyID(i)));
            writeVector(bodies.GetAngularVelocity(ragdoll->GetBodyID(i)));
            std::cout << ' ' << twistAngle << ' ' << swingY << ' ' << swingZ << ' ' << error << '\n';
        }
    };
    const int steps = rate * 4;
    for (int step = 0; step <= steps; ++step) {
        if (step == 0 || step == rate * 2) observe("ragdollimpulse ", step);
        if (step == 0) bodies.AddAngularImpulse(ragdoll->GetBodyID(2), axis * (0.6f * side));
        if (step == rate * 2) bodies.AddAngularImpulse(ragdoll->GetBodyID(2), axis * (-0.6f * side));
        observe("ragdolllimit ", step);
        if (step < steps && world.Update(1.0f / rate, 1, &allocator, &jobs) != JPH::EPhysicsUpdateError::None) return 5;
    }
    ragdoll->RemoveFromPhysicsSystem();
    ragdoll = nullptr;
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
    for (int rate : { 60, 120 }) for (int side : { -1, 1 }) for (int frame : { 0, 1 }) {
        if (result == 0) result = Physics3D::runLimits(rate, side, frame);
    }
    JPH::UnregisterTypes();
    JPH::Factory::sInstance = nullptr;
    return result;
}
