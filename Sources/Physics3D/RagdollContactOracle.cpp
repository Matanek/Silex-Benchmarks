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
#include <Jolt/Physics/Collision/BroadPhase/BroadPhaseLayerInterfaceTable.h>
#include <Jolt/Physics/Collision/BroadPhase/ObjectVsBroadPhaseLayerFilterTable.h>
#include <Jolt/Physics/Collision/ObjectLayerPairFilterTable.h>
#include <Jolt/Physics/Collision/GroupFilterTable.h>
#include <Jolt/Physics/Collision/Shape/SphereShape.h>
#include <Jolt/Physics/Collision/Shape/PlaneShape.h>
#include <Jolt/Physics/Constraints/SwingTwistConstraint.h>
#include <Jolt/Physics/Ragdoll/Ragdoll.h>
#include <Jolt/Skeleton/SkeletonPose.h>

namespace Physics3D {

// -----------------------------------------------------------------------------

void writeVector(JPH::Vec3Arg value) {
    std::cout << ' ' << value.GetX() << ' ' << value.GetY() << ' ' << value.GetZ();
}

void writeQuaternion(JPH::QuatArg value) {
    std::cout << ' ' << value.GetX() << ' ' << value.GetY() << ' ' << value.GetZ() << ' ' << value.GetW();
}

JPH::Quat target(int side, int phase) {
    const float direction = phase == 1 ? -1.0f : 1.0f;
    const float y = std::sin(0.25f * static_cast<float>(side) * direction);
    const float z = std::sin(-0.4f * direction);
    return JPH::Quat(0, y, z, std::sqrt(1 - y * y - z * z))
        * JPH::Quat::sRotation(JPH::Vec3::sAxisX(), phase == 1 ? -0.5f : 0.7f);
}

// -----------------------------------------------------------------------------

int runContact(int mode, int rate, int side, int frame) {
    JPH::BroadPhaseLayerInterfaceTable broadPhase(3, 1);
    for (JPH::ObjectLayer layer : { 0, 1, 2 }) broadPhase.MapObjectToBroadPhaseLayer(layer, JPH::BroadPhaseLayer(0));
    JPH::ObjectLayerPairFilterTable pairFilter(3);
    pairFilter.EnableCollision(1, 2);
    JPH::ObjectVsBroadPhaseLayerFilterTable phaseFilter(broadPhase, 1, pairFilter, 3);
    JPH::PhysicsSystem world;
    world.Init(16, 0, 16, 16, broadPhase, phaseFilter, pairFilter);
    auto physics = world.GetPhysicsSettings();
    physics.mNumVelocitySteps = 12; physics.mNumPositionSteps = 16;
    physics.mPenetrationSlop = 0.000001f;
    world.SetPhysicsSettings(physics); world.SetGravity(JPH::Vec3(0, -9.81f, 0));
    const auto base = JPH::Quat::sRotation(JPH::Vec3::sAxisY(), 0.7f * static_cast<float>(frame));
    const JPH::Vec3 anchor(0, 0.5f, 0);
    JPH::Ref<JPH::RagdollSettings> settings = new JPH::RagdollSettings;
    settings->mSkeleton = new JPH::Skeleton;
    settings->mSkeleton->AddJoint("root", -1); settings->mSkeleton->AddJoint("member", 0);
    JPH::Ref<JPH::GroupFilterTable> groups = new JPH::GroupFilterTable(2);
    groups->DisableCollision(0, 1);
    for (int i = 0; i < 2; ++i) {
        JPH::RagdollSettings::Part part;
        part.SetShape(new JPH::SphereShape(i == 0 ? 0.5f : 0.25f));
        part.mPosition = JPH::RVec3(anchor + base * JPH::Vec3(static_cast<float>(i), 0, 0));
        part.mRotation = base;
        part.mMotionType = i == 0 ? JPH::EMotionType::Static : JPH::EMotionType::Dynamic;
        part.mObjectLayer = i == 0 ? 0 : 1; part.mAllowSleeping = false;
        part.mLinearDamping = part.mAngularDamping = part.mFriction = part.mRestitution = 0;
        part.mCollisionGroup = JPH::CollisionGroup(groups, 1, i);
        if (i == 1) {
            part.mOverrideMassProperties = JPH::EOverrideMassProperties::MassAndInertiaProvided;
            part.mMassPropertiesOverride.mMass = 2;
            part.mMassPropertiesOverride.mInertia = JPH::Mat44::sScale(JPH::Vec3::sReplicate(0.2f));
            JPH::Ref<JPH::SwingTwistConstraintSettings> joint = new JPH::SwingTwistConstraintSettings;
            joint->mSpace = JPH::EConstraintSpace::LocalToBodyCOM;
            joint->mPosition1 = JPH::RVec3::sZero(); joint->mPosition2 = JPH::RVec3(-1, 0, 0);
            joint->mTwistAxis1 = joint->mTwistAxis2 = JPH::Vec3::sAxisX();
            joint->mPlaneAxis1 = joint->mPlaneAxis2 = JPH::Vec3::sAxisZ();
            joint->mPlaneHalfConeAngle = joint->mNormalHalfConeAngle = 0.6f;
            joint->mTwistMinAngle = -0.2f; joint->mTwistMaxAngle = 0.35f;
            for (auto* motor : { &joint->mTwistMotorSettings, &joint->mSwingMotorSettings }) {
                motor->mMinTorqueLimit = -30; motor->mMaxTorqueLimit = 30;
                motor->mSpringSettings = JPH::SpringSettings(JPH::ESpringMode::StiffnessAndDamping, 80, 15);
            }
            part.mToParent = joint;
        }
        settings->mParts.push_back(part);
    }
    settings->CalculateBodyIndexToConstraintIndex(); settings->CalculateConstraintIndexToBodyIdxPair();
    JPH::Ref<JPH::Ragdoll> ragdoll = settings->CreateRagdoll(1, 0, &world);
    if (!ragdoll) return 3;
    ragdoll->AddToPhysicsSystem(JPH::EActivation::Activate);
    auto& bodies = world.GetBodyInterface(); JPH::BodyID floor;
    if (mode == 1) {
        JPH::RefConst<JPH::PlaneShape> plane = new JPH::PlaneShape(JPH::Plane(JPH::Vec3::sAxisY(), 0));
        JPH::BodyCreationSettings floorSettings(plane, JPH::RVec3::sZero(), JPH::Quat::sIdentity(), JPH::EMotionType::Static, 2);
        floorSettings.mFriction = floorSettings.mRestitution = 0;
        floor = bodies.CreateAndAddBody(floorSettings, JPH::EActivation::DontActivate);
        if (floor.IsInvalid()) return 3;
    }
    auto* joint = static_cast<JPH::SwingTwistConstraint*>(ragdoll->GetConstraint(0));
    const auto body = ragdoll->GetBodyID(1); const float delta = 1.0f / static_cast<float>(rate);
    auto observe = [&](const char* label, int step, JPH::Vec3Arg before) {
        const auto p = bodies.GetPosition(body); const auto q = bodies.GetRotation(body);
        const auto v = bodies.GetLinearVelocity(body); const auto w = bodies.GetAngularVelocity(body);
        const auto e = JPH::Vec3(p + q * JPH::Vec3(-1, 0, 0)) - anchor;
        const int contact = !floor.IsInvalid() && world.WereBodiesInContact(floor, body) ? 1 : 0;
        std::cout << label << ' ' << mode << ' ' << rate << ' ' << side << ' ' << frame << ' ' << step;
        writeVector(JPH::Vec3(p)); writeQuaternion(q); writeVector(v); writeVector(w);
        writeQuaternion(joint->GetRotationInConstraintSpace()); writeVector(q.Conjugated() * w);
        writeVector(joint->GetTotalLambdaMotor() / delta); writeVector(e);
        writeVector(joint->GetTotalLambdaPosition() / delta);
        // Solved contact impulses are unavailable through Jolt's public API.
        // Flag zero requests independent inference from the linear balance.
        std::cout << ' ' << 0 << ' ' << contact << ' ' << 0;
        writeVector(before); std::cout << '\n';
    };
    JPH::SkeletonPose pose; pose.SetSkeleton(settings->mSkeleton);
    JPH::TempAllocatorImpl allocator(1024 * 1024); JPH::JobSystemSingleThreaded jobs(JPH::cMaxPhysicsJobs);
    int step = 0; observe("ragdollcontact", step, JPH::Vec3::sZero());
    while (step < rate * 14) {
        if (step == 0 || step == rate * 4 || step == rate * 8 || step == rate * 12) {
            observe("ragdollbefore", step, bodies.GetLinearVelocity(body));
            if (step == rate * 12) {
                joint->SetTwistMotorState(JPH::EMotorState::Off); joint->SetSwingMotorState(JPH::EMotorState::Off);
                joint->ResetWarmStart(); bodies.AddAngularImpulse(body, bodies.GetRotation(body) * JPH::Vec3(0.2f, 0, 0));
            } else {
                pose.GetJoint(0).mRotation = base; pose.GetJoint(1).mRotation = target(side, step == rate * 4 ? 1 : 0);
                pose.CalculateJointMatrices(); ragdoll->DriveToPoseUsingMotors(pose); joint->ResetWarmStart();
            }
            observe("ragdollafter", step, bodies.GetLinearVelocity(body));
        }
        const auto before = bodies.GetLinearVelocity(body);
        if (world.Update(delta, 1, &allocator, &jobs) != JPH::EPhysicsUpdateError::None) return 4;
        observe("ragdollcontact", ++step, before);
    }
    ragdoll->RemoveFromPhysicsSystem();
    if (!floor.IsInvalid()) { bodies.RemoveBody(floor); bodies.DestroyBody(floor); }
    return 0;
}

// -----------------------------------------------------------------------------

} // namespace Physics3D

int main() {
#ifdef JPH_ENABLE_ASSERTS
    JPH::AssertFailed = [](const char* expression, const char*, const char*, JPH::uint) {
        std::cerr << "Jolt assertion: " << expression << '\n'; std::abort(); return false;
    };
#endif
    JPH::RegisterDefaultAllocator(); auto factory = std::make_unique<JPH::Factory>();
    JPH::Factory::sInstance = factory.get(); JPH::RegisterTypes(); std::cout.precision(9);
    int result = 0;
    for (int mode : { 0, 1 }) for (int rate : { 60, 120 }) for (int side : { -1, 1 }) for (int frame : { 0, 1 }) {
        if (result == 0) result = Physics3D::runContact(mode, rate, side, frame);
    }
    JPH::UnregisterTypes(); JPH::Factory::sInstance = nullptr; return result;
}
