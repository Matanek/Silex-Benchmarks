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
#include <Jolt/Physics/Constraints/RackAndPinionConstraint.h>

namespace Physics3D {

// -----------------------------------------------------------------------------

int runRackAndPinionCase(int caseId) {
    constexpr std::array<float, 7> ratios = {1, 2, -2, 0.5f, 2, 2, 2};
    float ratio = ratios[caseId];
    float rackMass = caseId == 4 ? 8.0f : 2.0f;
    auto rotation = caseId == 5 ? JPH::Quat::sRotation(JPH::Vec3::sAxisY(), 0.7f) : JPH::Quat::sIdentity();
    auto pinionAxis = rotation * JPH::Vec3::sAxisZ();
    auto rackAxis = rotation * JPH::Vec3::sAxisX();
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
    settings.mMassPropertiesOverride.mMass = rackMass;
    auto* second = bodies.CreateBody(settings);
    if (!first || !second) return 3;
    bodies.AddBody(first->GetID(), JPH::EActivation::Activate);
    bodies.AddBody(second->GetID(), JPH::EActivation::Activate);
    JPH::RackAndPinionConstraintSettings coupling;
    coupling.mSpace = JPH::EConstraintSpace::LocalToBodyCOM;
    coupling.mHingeAxis = JPH::Vec3::sAxisZ();
    coupling.mSliderAxis = JPH::Vec3::sAxisX();
    coupling.mRatio = ratio;
    JPH::Ref<JPH::RackAndPinionConstraint> joint = new JPH::RackAndPinionConstraint(*first, *second, coupling);
    world.AddConstraint(joint.GetPtr());
    bodies.SetLinearVelocity(second->GetID(), rackAxis);
    JPH::TempAllocatorImpl allocator(1024 * 1024);
    JPH::JobSystemSingleThreaded jobs(JPH::cMaxPhysicsJobs);
    for (int step = 1; step <= 360; ++step) {
        if (caseId == 6) bodies.AddForce(second->GetID(), rackAxis * 0.1f);
        if (world.Update(1.0f / 60.0f, 1, &allocator, &jobs) != JPH::EPhysicsUpdateError::None) return 4;
        if (step == 1 || step % 15 == 0) {
            float w = bodies.GetAngularVelocity(first->GetID()).Dot(pinionAxis);
            float v = bodies.GetLinearVelocity(second->GetID()).Dot(rackAxis);
            float lambda = joint->GetTotalLambda() * 60;
            float travel = JPH::Vec3(bodies.GetPosition(second->GetID())).Dot(rackAxis);
            auto relative = rotation.Conjugated() * bodies.GetRotation(first->GetID());
            float angle = 2 * std::atan2(relative.GetZ(), relative.GetW());
            angle -= 2 * JPH::JPH_PI * std::floor((angle + JPH::JPH_PI) / (2 * JPH::JPH_PI));
            std::cout << "rack " << caseId << ' ' << step << ' ' << angle << ' ' << travel << ' ' << w << ' ' << v << ' ' << lambda << ' ' << -ratio * lambda << '\n';
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
    for (int caseId = 0; caseId < 7 && result == 0; ++caseId) result = Physics3D::runRackAndPinionCase(caseId);
    JPH::UnregisterTypes();
    JPH::Factory::sInstance = nullptr;
    return result;
}
