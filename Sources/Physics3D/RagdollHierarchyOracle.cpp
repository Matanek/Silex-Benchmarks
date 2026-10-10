#include <array>
#include <cstdlib>
#include <iostream>
#include <memory>
#include <Jolt/Jolt.h>
#include <Jolt/RegisterTypes.h>
#include <Jolt/Core/Factory.h>
#include <Jolt/Core/IssueReporting.h>
#include <Jolt/Physics/PhysicsSystem.h>
#include <Jolt/Physics/Body/Body.h>
#include <Jolt/Physics/Collision/BroadPhase/BroadPhaseLayerInterfaceTable.h>
#include <Jolt/Physics/Collision/BroadPhase/ObjectVsBroadPhaseLayerFilterTable.h>
#include <Jolt/Physics/Collision/ObjectLayerPairFilterTable.h>
#include <Jolt/Physics/Collision/Shape/SphereShape.h>
#include <Jolt/Physics/Constraints/SwingTwistConstraint.h>
#include <Jolt/Physics/Ragdoll/Ragdoll.h>

namespace Physics3D {

// -----------------------------------------------------------------------------

void writeTransform(const JPH::Mat44& value) {
    const auto p = value.GetTranslation();
    const auto q = value.GetQuaternion();
    std::cout << ' ' << p.GetX() << ' ' << p.GetY() << ' ' << p.GetZ()
        << ' ' << q.GetX() << ' ' << q.GetY() << ' ' << q.GetZ() << ' ' << q.GetW();
}

int runHierarchy() {
    JPH::BroadPhaseLayerInterfaceTable broadPhase(1, 1);
    broadPhase.MapObjectToBroadPhaseLayer(0, JPH::BroadPhaseLayer(0));
    JPH::ObjectLayerPairFilterTable pairFilter(1);
    JPH::ObjectVsBroadPhaseLayerFilterTable phaseFilter(broadPhase, 1, pairFilter, 1);
    JPH::PhysicsSystem world;
    world.Init(16, 0, 16, 16, broadPhase, phaseFilter, pairFilter);
    const float halfPi = JPH::JPH_PI / 2;
    const auto transform = [](JPH::Vec3Arg p, JPH::QuatArg q) { return JPH::Mat44::sRotationTranslation(q, p); };
    const std::array<JPH::Mat44, 3> local {
        JPH::Mat44::sIdentity(),
        transform(JPH::Vec3(1, 0, 0), JPH::Quat::sRotation(JPH::Vec3::sAxisZ(), halfPi)),
        transform(JPH::Vec3(0, 2, 0), JPH::Quat::sRotation(JPH::Vec3::sAxisX(), halfPi))
    };
    const std::array<JPH::Mat44, 3> offsets {
        transform(JPH::Vec3(0.2f, 0, 0), JPH::Quat::sRotation(JPH::Vec3::sAxisX(), 0.3f)),
        transform(JPH::Vec3(0, 0.3f, 0), JPH::Quat::sRotation(JPH::Vec3::sAxisY(), 0.2f)),
        JPH::Mat44::sTranslation(JPH::Vec3(0, 0, 0.4f))
    };
    const std::array<JPH::Mat44, 3> rest { local[0], local[1], local[1] * local[2] };
    JPH::Ref<JPH::RagdollSettings> settings = new JPH::RagdollSettings;
    settings->mSkeleton = new JPH::Skeleton;
    settings->mSkeleton->AddJoint("root", -1);
    settings->mSkeleton->AddJoint("child", 0);
    settings->mSkeleton->AddJoint("leaf", 1);
    JPH::RefConst<JPH::SphereShape> shape = new JPH::SphereShape(0.3f);
    for (int i = 0; i < 3; ++i) {
        const auto body = rest[i] * offsets[i];
        JPH::RagdollSettings::Part part;
        part.SetShape(shape);
        part.mPosition = JPH::RVec3(body.GetTranslation());
        part.mRotation = body.GetQuaternion();
        part.mMotionType = JPH::EMotionType::Dynamic;
        part.mObjectLayer = 0;
        if (i > 0) {
            JPH::Ref<JPH::SwingTwistConstraintSettings> joint = new JPH::SwingTwistConstraintSettings;
            joint->mPosition1 = joint->mPosition2 = JPH::RVec3(rest[i].GetTranslation());
            joint->mTwistAxis1 = joint->mTwistAxis2 = rest[i].Multiply3x3(JPH::Vec3::sAxisX());
            joint->mPlaneAxis1 = joint->mPlaneAxis2 = rest[i].Multiply3x3(JPH::Vec3::sAxisZ());
            part.mToParent = joint;
        }
        settings->mParts.push_back(part);
    }
    settings->DisableParentChildCollisions();
    settings->CalculateBodyIndexToConstraintIndex();
    settings->CalculateConstraintIndexToBodyIdxPair();
    std::array<JPH::Ref<JPH::Ragdoll>, 2> ragdolls;
    for (int instance = 0; instance < 2; ++instance) {
        ragdolls[instance] = settings->CreateRagdoll(instance + 1, 0, &world);
        if (!ragdolls[instance]) return 3;
        ragdolls[instance]->AddToPhysicsSystem(JPH::EActivation::Activate);
        for (int stage = 0; stage < 2; ++stage) {
            const auto root = stage == 0
                ? transform(JPH::Vec3(3.0f + instance * 10.0f, 4, 5), JPH::Quat::sRotation(JPH::Vec3::sAxisY(), halfPi))
                : transform(JPH::Vec3(-2.0f + instance * 10.0f, 3, 1), JPH::Quat::sRotation(JPH::Vec3::sAxisX(), 0.8f));
            std::array<JPH::Mat44, 3> bodyPose;
            for (int i = 0; i < 3; ++i) bodyPose[i] = root * rest[i] * offsets[i];
            ragdolls[instance]->SetPose(JPH::RVec3::sZero(), bodyPose.data());
            ragdolls[instance]->ResetWarmStart();
            JPH::RVec3 rootOffset;
            ragdolls[instance]->GetPose(rootOffset, bodyPose.data());
            for (int i = 0; i < 3; ++i) {
                const auto body = JPH::Mat44::sTranslation(JPH::Vec3(rootOffset)) * bodyPose[i];
                std::cout << "pose " << instance << ' ' << stage << ' ' << i;
                writeTransform(body * offsets[i].InversedRotationTranslation());
                writeTransform(body);
                std::cout << '\n';
            }
        }
    }
    int own = 0;
    int cross = 0;
    const auto group = [&](int instance, int part) -> const JPH::CollisionGroup& {
        return world.GetBodyLockInterfaceNoLock().TryGetBody(ragdolls[instance]->GetBodyID(part))->GetCollisionGroup();
    };
    for (int i = 0; i < 3; ++i) {
        for (int j = i + 1; j < 3; ++j) own += group(0, i).CanCollide(group(0, j));
        for (int j = 0; j < 3; ++j) cross += group(0, i).CanCollide(group(1, j));
    }
    std::cout << "filter own " << own << "\nfilter cross " << cross << '\n';
    for (auto& ragdoll : ragdolls) {
        ragdoll->RemoveFromPhysicsSystem();
        ragdoll = nullptr;
    }
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
    const int result = Physics3D::runHierarchy();
    JPH::UnregisterTypes();
    JPH::Factory::sInstance = nullptr;
    return result;
}
