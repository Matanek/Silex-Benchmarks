#include <array>
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
#include <Jolt/Physics/Constraints/GearConstraint.h>

namespace Physics3D {

// -----------------------------------------------------------------------------

int runGearCase(int caseId) {
    constexpr float ratio = 1;
    float secondInertia = caseId == 1 ? 0.8f : 0.2f;
    auto rotation = caseId == 2 ? JPH::Quat::sRotation(JPH::Vec3::sAxisY(), 0.7f) : JPH::Quat::sIdentity();
    auto firstAxis = rotation * JPH::Vec3::sAxisZ();
    auto secondAxis = caseId == 3 ? JPH::Vec3::sAxisX() : firstAxis;
    JPH::BroadPhaseLayerInterfaceTable broadPhase(1, 1);
    broadPhase.MapObjectToBroadPhaseLayer(0, JPH::BroadPhaseLayer(0));
    JPH::ObjectLayerPairFilterTable pairFilter(1);
    JPH::ObjectVsBroadPhaseLayerFilterTable phaseFilter(broadPhase, 1, pairFilter, 1);
    JPH::PhysicsSystem world;
    world.Init(16, 0, 16, 16, broadPhase, phaseFilter, pairFilter);
    auto physicsSettings = world.GetPhysicsSettings();
    physicsSettings.mNumVelocitySteps = 24;
    physicsSettings.mNumPositionSteps = 8;
    world.SetPhysicsSettings(physicsSettings);
    world.SetGravity(JPH::Vec3::sZero());
    JPH::RefConst<JPH::SphereShape> sphere = new JPH::SphereShape(0.25f);
    JPH::BodyCreationSettings settings(sphere, JPH::RVec3::sZero(), JPH::Quat::sIdentity(), JPH::EMotionType::Dynamic, 0);
    settings.mAllowSleeping = false;
    settings.mLinearDamping = settings.mAngularDamping = 0;
    settings.mOverrideMassProperties = JPH::EOverrideMassProperties::MassAndInertiaProvided;
    settings.mMassPropertiesOverride.mMass = 2;
    settings.mMassPropertiesOverride.mInertia = JPH::Mat44::sScale(JPH::Vec3::sReplicate(0.2f));
    auto& bodies = world.GetBodyInterface();
    settings.mRotation = rotation;
    auto* first = bodies.CreateBody(settings);
    settings.mRotation = caseId == 3 ? JPH::Quat::sRotation(JPH::Vec3::sAxisY(), 0.5f * JPH::JPH_PI) : rotation;
    settings.mMassPropertiesOverride.mInertia = JPH::Mat44::sScale(JPH::Vec3::sReplicate(secondInertia));
    auto* second = bodies.CreateBody(settings);
    if (!first || !second) return 3;
    bodies.AddBody(first->GetID(), JPH::EActivation::Activate);
    bodies.AddBody(second->GetID(), JPH::EActivation::Activate);
    JPH::GearConstraintSettings coupling;
    coupling.mSpace = JPH::EConstraintSpace::LocalToBodyCOM;
    coupling.mHingeAxis1 = coupling.mHingeAxis2 = JPH::Vec3::sAxisZ();
    coupling.mRatio = ratio;
    JPH::Ref<JPH::GearConstraint> joint = new JPH::GearConstraint(*first, *second, coupling);
    world.AddConstraint(joint.GetPtr());
    bodies.SetAngularVelocity(second->GetID(), secondAxis);
    if (caseId == 4) bodies.SetAngularVelocity(first->GetID(), firstAxis * 0.25f);
    JPH::TempAllocatorImpl allocator(1024 * 1024);
    JPH::JobSystemSingleThreaded jobs(JPH::cMaxPhysicsJobs);
    for (int step = 1; step <= 360; ++step) {
        if (caseId == 5) bodies.AddTorque(second->GetID(), secondAxis * 0.1f);
        if (world.Update(1.0f / 60.0f, 1, &allocator, &jobs) != JPH::EPhysicsUpdateError::None) return 4;
        if (step == 1 || step % 15 == 0) {
            float a = bodies.GetAngularVelocity(first->GetID()).Dot(firstAxis);
            float b = bodies.GetAngularVelocity(second->GetID()).Dot(secondAxis);
            float lambda = joint->GetTotalLambda() * 60;
            std::cout << "gear " << caseId << ' ' << step << ' ' << a << ' ' << b << ' ' << lambda << '\n';
        }
    }
    world.RemoveConstraint(joint.GetPtr());
    bodies.RemoveBody(first->GetID()); bodies.RemoveBody(second->GetID());
    bodies.DestroyBody(first->GetID()); bodies.DestroyBody(second->GetID());
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
    for (int caseId = 0; caseId < 6 && result == 0; ++caseId) result = Physics3D::runGearCase(caseId);
    JPH::UnregisterTypes();
    JPH::Factory::sInstance = nullptr;
    return result;
}
