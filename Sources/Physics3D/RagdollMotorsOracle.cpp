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
#include <Jolt/Physics/Collision/BroadPhase/BroadPhaseLayerInterfaceTable.h>
#include <Jolt/Physics/Collision/BroadPhase/ObjectVsBroadPhaseLayerFilterTable.h>
#include <Jolt/Physics/Collision/ObjectLayerPairFilterTable.h>
#include <Jolt/Physics/Collision/GroupFilterTable.h>
#include <Jolt/Physics/Collision/Shape/SphereShape.h>
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

int runMotors(int rate, int side) {
    JPH::BroadPhaseLayerInterfaceTable broadPhase(1, 1);
    broadPhase.MapObjectToBroadPhaseLayer(0, JPH::BroadPhaseLayer(0));
    JPH::ObjectLayerPairFilterTable pairFilter(1);
    JPH::ObjectVsBroadPhaseLayerFilterTable phaseFilter(broadPhase, 1, pairFilter, 1);
    JPH::PhysicsSystem world;
    world.Init(16, 0, 16, 16, broadPhase, phaseFilter, pairFilter);
    auto physics = world.GetPhysicsSettings();
    physics.mNumVelocitySteps = 12;
    physics.mNumPositionSteps = 16;
    world.SetPhysicsSettings(physics);
    world.SetGravity(JPH::Vec3(0, -9.81f, 0));
    const auto base = JPH::Quat::sRotation(JPH::Vec3(1, 2, -1).Normalized(), 0.6f);
    const std::array<JPH::Vec3, 3> localPositions { JPH::Vec3::sZero(), JPH::Vec3(0, -0.5f, 0), JPH::Vec3(0, -0.8f, 0) };
    const std::array<JPH::Quat, 3> localRotations { JPH::Quat::sIdentity(), JPH::Quat::sRotation(JPH::Vec3::sAxisZ(), 0.4f), JPH::Quat::sRotation(JPH::Vec3::sAxisY(), -0.3f) };
    const std::array<JPH::Vec3, 3> offsets { JPH::Vec3::sReplicate(0.1f), JPH::Vec3(0, -0.4f, 0), JPH::Vec3(0, -0.3f, 0) };
    const std::array<JPH::Quat, 3> offsetRotations { JPH::Quat::sRotation(JPH::Vec3::sAxisY(), 0.2f), JPH::Quat::sRotation(JPH::Vec3::sAxisX(), 0.3f), JPH::Quat::sRotation(JPH::Vec3::sAxisZ(), -0.2f) };
    std::array<JPH::Vec3, 3> jointPositions;
    std::array<JPH::Quat, 3> jointRotations;
    std::array<JPH::Vec3, 3> bodyPositions;
    std::array<JPH::Quat, 3> bodyRotations;
    std::array<JPH::Vec3, 2> firstAnchors;
    std::array<JPH::Vec3, 2> secondAnchors;
    std::array<JPH::Quat, 2> secondFrames;
    JPH::Ref<JPH::RagdollSettings> settings = new JPH::RagdollSettings;
    settings->mSkeleton = new JPH::Skeleton;
    settings->mSkeleton->AddJoint("root", -1);
    settings->mSkeleton->AddJoint("child", 0);
    settings->mSkeleton->AddJoint("leaf", 1);
    JPH::RefConst<JPH::SphereShape> shape = new JPH::SphereShape(0.5f);
    JPH::Ref<JPH::GroupFilterTable> groups = new JPH::GroupFilterTable(3);
    for (int i = 0; i < 3; ++i) for (int j = i + 1; j < 3; ++j) groups->DisableCollision(i, j);
    for (int i = 0; i < 3; ++i) {
        jointPositions[i] = i == 0 ? JPH::Vec3(0, 3, 0) : jointPositions[i - 1] + jointRotations[i - 1] * localPositions[i];
        jointRotations[i] = i == 0 ? base : jointRotations[i - 1] * localRotations[i];
        bodyPositions[i] = jointPositions[i] + jointRotations[i] * offsets[i];
        bodyRotations[i] = jointRotations[i] * offsetRotations[i];
        JPH::RagdollSettings::Part part;
        part.SetShape(shape);
        part.mPosition = JPH::RVec3(bodyPositions[i]);
        part.mRotation = bodyRotations[i];
        part.mMotionType = i == 0 ? JPH::EMotionType::Static : JPH::EMotionType::Dynamic;
        part.mObjectLayer = 0;
        part.mAllowSleeping = false;
        part.mLinearDamping = part.mAngularDamping = 0;
        part.mOverrideMassProperties = JPH::EOverrideMassProperties::MassAndInertiaProvided;
        part.mMassPropertiesOverride.mMass = 1;
        part.mMassPropertiesOverride.mInertia = JPH::Mat44::sScale(JPH::Vec3::sReplicate(0.2f));
        part.mCollisionGroup = JPH::CollisionGroup(groups, 1, i);
        if (i > 0) {
            firstAnchors[i - 1] = bodyRotations[i - 1].Conjugated() * (jointPositions[i] - bodyPositions[i - 1]);
            secondAnchors[i - 1] = bodyRotations[i].Conjugated() * (jointPositions[i] - bodyPositions[i]);
            const auto firstFrame = bodyRotations[i - 1].Conjugated() * jointRotations[i];
            secondFrames[i - 1] = bodyRotations[i].Conjugated() * jointRotations[i];
            JPH::Ref<JPH::SwingTwistConstraintSettings> joint = new JPH::SwingTwistConstraintSettings;
            joint->mSpace = JPH::EConstraintSpace::LocalToBodyCOM;
            joint->mPosition1 = JPH::RVec3(firstAnchors[i - 1]);
            joint->mPosition2 = JPH::RVec3(secondAnchors[i - 1]);
            joint->mTwistAxis1 = firstFrame * JPH::Vec3::sAxisX();
            joint->mTwistAxis2 = secondFrames[i - 1] * JPH::Vec3::sAxisX();
            joint->mPlaneAxis1 = firstFrame * JPH::Vec3::sAxisZ();
            joint->mPlaneAxis2 = secondFrames[i - 1] * JPH::Vec3::sAxisZ();
            joint->mPlaneHalfConeAngle = joint->mNormalHalfConeAngle = 0.8f;
            joint->mTwistMinAngle = -0.8f;
            joint->mTwistMaxAngle = 0.8f;
            for (auto* motor : { &joint->mTwistMotorSettings, &joint->mSwingMotorSettings }) {
                motor->mMinTorqueLimit = -120;
                motor->mMaxTorqueLimit = 120;
                motor->mSpringSettings = JPH::SpringSettings(JPH::ESpringMode::StiffnessAndDamping, 400, 40);
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
    JPH::SkeletonPose pose;
    pose.SetSkeleton(settings->mSkeleton);
    JPH::TempAllocatorImpl allocator(1024 * 1024);
    JPH::JobSystemSingleThreaded jobs(JPH::cMaxPhysicsJobs);
    const float delta = 1.0f / rate;
    for (int step = 0; step <= rate * 13; ++step) {
        if (step == 0 || step == rate * 4 || step == rate * 8) {
            float direction = static_cast<float>(side);
            if (step == rate * 4) direction = -direction;
            if (step == rate * 8) direction = 0;
            const auto target = JPH::Quat::sRotation(JPH::Vec3::sAxisZ(), 0.25f * direction) * JPH::Quat::sRotation(JPH::Vec3::sAxisX(), 0.2f * direction);
            pose.GetJoint(0).mRotation = base * offsetRotations[0];
            for (int i = 1; i < 3; ++i) {
                const auto jointTarget = localRotations[i] * (i == 1 ? target : target.Conjugated());
                pose.GetJoint(i).mRotation = offsetRotations[i - 1].Conjugated() * jointTarget * offsetRotations[i];
            }
            pose.CalculateJointMatrices();
            ragdoll->DriveToPoseUsingMotors(pose);
            for (int i = 0; i < 2; ++i) ragdoll->GetConstraint(i)->ResetWarmStart();
        }
        if (step == rate * 12) for (int i = 0; i < 2; ++i) {
            auto* joint = static_cast<JPH::SwingTwistConstraint*>(ragdoll->GetConstraint(i));
            joint->SetTwistMotorState(JPH::EMotorState::Off);
            joint->SetSwingMotorState(JPH::EMotorState::Off);
            joint->ResetWarmStart();
        }
        for (int i = 1; i < 3; ++i) {
            auto* joint = static_cast<JPH::SwingTwistConstraint*>(ragdoll->GetConstraint(i - 1));
            const auto firstRotation = bodies.GetRotation(ragdoll->GetBodyID(i - 1));
            const auto secondRotation = bodies.GetRotation(ragdoll->GetBodyID(i));
            const auto frame = secondRotation * secondFrames[i - 1];
            const auto speed = frame.Conjugated() * (bodies.GetAngularVelocity(ragdoll->GetBodyID(i)) - bodies.GetAngularVelocity(ragdoll->GetBodyID(i - 1)));
            const auto firstPoint = bodies.GetPosition(ragdoll->GetBodyID(i - 1)) + firstRotation * firstAnchors[i - 1];
            const auto secondPoint = bodies.GetPosition(ragdoll->GetBodyID(i)) + secondRotation * secondAnchors[i - 1];
            std::cout << "ragdollmotor " << rate << ' ' << side << ' ' << step << ' ' << i;
            writeVector(JPH::Vec3(bodies.GetCenterOfMassPosition(ragdoll->GetBodyID(i))));
            writeQuaternion(secondRotation);
            writeVector(bodies.GetLinearVelocity(ragdoll->GetBodyID(i)));
            writeVector(bodies.GetAngularVelocity(ragdoll->GetBodyID(i)));
            writeQuaternion(joint->GetRotationInConstraintSpace());
            writeVector(speed);
            writeVector(joint->GetTotalLambdaMotor() / delta);
            writeVector(JPH::Vec3(secondPoint - firstPoint));
            std::cout << '\n';
        }
        if (step < rate * 13 && world.Update(delta, 1, &allocator, &jobs) != JPH::EPhysicsUpdateError::None) return 4;
    }
    ragdoll->RemoveFromPhysicsSystem();
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
    for (int rate : { 60, 120 }) for (int side : { -1, 1 }) {
        if (result == 0) result = Physics3D::runMotors(rate, side);
    }
    JPH::UnregisterTypes();
    JPH::Factory::sInstance = nullptr;
    return result;
}
