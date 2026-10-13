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

// -----------------------------------------------------------------------------

int runMobileContact(int rate, int side, int frame) {
    JPH::BroadPhaseLayerInterfaceTable broadPhase(2, 1);
    broadPhase.MapObjectToBroadPhaseLayer(0, JPH::BroadPhaseLayer(0));
    broadPhase.MapObjectToBroadPhaseLayer(1, JPH::BroadPhaseLayer(0));
    JPH::ObjectLayerPairFilterTable pairFilter(2);
    pairFilter.EnableCollision(0, 1);
    JPH::ObjectVsBroadPhaseLayerFilterTable phaseFilter(broadPhase, 1, pairFilter, 2);
    JPH::PhysicsSystem world;
    world.Init(16, 0, 16, 16, broadPhase, phaseFilter, pairFilter);
    world.SetGravity(JPH::Vec3(0, -9.81f, 0));
    auto physicsSettings = world.GetPhysicsSettings();
    physicsSettings.mNumPositionSteps = 16;
    physicsSettings.mNumVelocitySteps = 24;
    physicsSettings.mPenetrationSlop = 0.000001f;
    world.SetPhysicsSettings(physicsSettings);
    const auto base = JPH::Quat::sRotation(JPH::Vec3::sAxisY(), 0.7f * static_cast<float>(frame));
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
        part.mPosition = JPH::RVec3(0, 1, 0) + base * JPH::Vec3(static_cast<float>(i), 0, 0);
        part.mRotation = base;
        part.mMotionType = JPH::EMotionType::Dynamic;
        part.mObjectLayer = 1;
        part.mAllowSleeping = false;
        part.mLinearDamping = part.mAngularDamping = part.mFriction = part.mRestitution = 0;
        part.mOverrideMassProperties = JPH::EOverrideMassProperties::MassAndInertiaProvided;
        part.mMassPropertiesOverride.mMass = 2;
        part.mMassPropertiesOverride.mInertia = JPH::Mat44::sScale(JPH::Vec3::sReplicate(0.2f));
        part.mCollisionGroup = JPH::CollisionGroup(groups, 1, i);
        if (i > 0) {
            JPH::Ref<JPH::SwingTwistConstraintSettings> joint = new JPH::SwingTwistConstraintSettings;
            joint->mSpace = JPH::EConstraintSpace::LocalToBodyCOM;
            joint->mPosition1 = JPH::RVec3(0.5f, 0, 0);
            joint->mPosition2 = JPH::RVec3(-0.5f, 0, 0);
            joint->mTwistAxis1 = joint->mTwistAxis2 = JPH::Vec3::sAxisX();
            joint->mPlaneAxis1 = joint->mPlaneAxis2 = JPH::Vec3::sAxisZ();
            joint->mPlaneHalfConeAngle = joint->mNormalHalfConeAngle = 0.6f;
            joint->mTwistMinAngle = -0.2f;
            joint->mTwistMaxAngle = 0.35f;
            for (auto* motor : { &joint->mTwistMotorSettings, &joint->mSwingMotorSettings }) {
                motor->mMinTorqueLimit = -30;
                motor->mMaxTorqueLimit = 30;
                motor->mSpringSettings = JPH::SpringSettings(JPH::ESpringMode::StiffnessAndDamping, 80, 15);
            }
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
    JPH::RefConst<JPH::PlaneShape> plane = new JPH::PlaneShape(JPH::Plane(JPH::Vec3::sAxisY(), 0));
    JPH::BodyCreationSettings floorSettings(plane, JPH::RVec3::sZero(), JPH::Quat::sIdentity(), JPH::EMotionType::Static, 0);
    floorSettings.mFriction = floorSettings.mRestitution = 0;
    const auto floor = bodies.CreateAndAddBody(floorSettings, JPH::EActivation::DontActivate);
    if (floor.IsInvalid()) return 3;
    JPH::TempAllocatorImpl allocator(1024 * 1024);
    JPH::JobSystemSingleThreaded jobs(JPH::cMaxPhysicsJobs);
    const float delta = 1.0f / static_cast<float>(rate);
    const auto observe = [&](const char* label, int step) {
        for (int i = 0; i < 3; ++i) {
            const auto body = ragdoll->GetBodyID(i);
            const auto q = bodies.GetRotation(body);
            JPH::Quat orientation = JPH::Quat::sIdentity();
            auto motor = JPH::Vec3::sZero();
            auto force = JPH::Vec3::sZero();
            auto error = JPH::Vec3::sZero();
            if (i > 0) {
                const auto* joint = static_cast<const JPH::SwingTwistConstraint*>(ragdoll->GetConstraint(i - 1));
                orientation = joint->GetRotationInConstraintSpace();
                motor = joint->GetTotalLambdaMotor() / delta;
                force = joint->GetTotalLambdaPosition() / delta;
                const auto first = bodies.GetPosition(ragdoll->GetBodyID(i - 1))
                    + bodies.GetRotation(ragdoll->GetBodyID(i - 1)) * JPH::Vec3(0.5f, 0, 0);
                const auto second = bodies.GetPosition(body) + q * JPH::Vec3(-0.5f, 0, 0);
                error = JPH::Vec3(second - first);
            }
            std::cout << label << ' ' << rate << ' ' << side << ' ' << frame << ' ' << step << ' ' << i;
            writeVector(JPH::Vec3(bodies.GetPosition(body)));
            writeQuaternion(q);
            writeVector(bodies.GetLinearVelocity(body));
            writeVector(bodies.GetAngularVelocity(body));
            writeQuaternion(orientation);
            writeVector(motor);
            writeVector(force);
            writeVector(error);
            const int contact = world.WereBodiesInContact(floor, body) ? 1 : 0;
            std::cout << ' ' << 0 << ' ' << contact << ' ' << 0 << '\n';
        }
    };
    JPH::SkeletonPose pose;
    pose.SetSkeleton(settings->mSkeleton);
    int step = 0;
    observe("mobilecontact", step);
    while (step < rate * 12) {
        if (step == rate * 2 || step == rate * 4 || step == rate * 7 || step == rate * 10) {
            observe("mobilebefore", step);
            if (step == rate * 10) {
                for (int i = 0; i < 2; ++i) {
                    auto* joint = static_cast<JPH::SwingTwistConstraint*>(ragdoll->GetConstraint(i));
                    joint->SetTwistMotorState(JPH::EMotorState::Off);
                    joint->SetSwingMotorState(JPH::EMotorState::Off);
                    joint->ResetWarmStart();
                }
                for (int i = 0; i < 3; ++i) bodies.AddImpulse(ragdoll->GetBodyID(i), JPH::Vec3(0, 4, 0));
            } else {
                float angle = 0;
                if (step == rate * 4) angle = 0.8f * static_cast<float>(side);
                if (step == rate * 7) angle = -0.8f * static_cast<float>(side);
                pose.GetJoint(0).mRotation = base;
                pose.GetJoint(1).mRotation = JPH::Quat::sRotation(JPH::Vec3::sAxisZ(), angle);
                pose.GetJoint(2).mRotation = JPH::Quat::sRotation(JPH::Vec3::sAxisZ(), -angle);
                pose.CalculateJointMatrices();
                ragdoll->DriveToPoseUsingMotors(pose);
                for (int i = 0; i < 2; ++i) ragdoll->GetConstraint(i)->ResetWarmStart();
            }
            observe("mobileafter", step);
        }
        if (world.Update(delta, 1, &allocator, &jobs) != JPH::EPhysicsUpdateError::None) return 5;
        observe("mobilecontact", ++step);
    }
    ragdoll->RemoveFromPhysicsSystem();
    ragdoll = nullptr;
    bodies.RemoveBody(floor);
    bodies.DestroyBody(floor);
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
        if (result == 0) result = Physics3D::runMobileContact(rate, side, frame);
    }
    JPH::UnregisterTypes();
    JPH::Factory::sInstance = nullptr;
    return result;
}
