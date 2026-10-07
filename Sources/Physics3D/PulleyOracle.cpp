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
#include <Jolt/Physics/Constraints/PulleyConstraint.h>

namespace Physics3D {

// -----------------------------------------------------------------------------

int runPulleyCase(int caseId) {
    constexpr std::array<float, 10> ratios = {1, 2, 0.5f, 1, 2, 1, 1, 1, 1, 1};
    float ratio = ratios[caseId];
    float secondMass = (caseId == 1 || caseId == 8) ? 8.0f : (caseId == 4 ? 4.0f : 2.0f);
    float height = caseId == 8 ? 200.0f : 10.0f;
    auto rotation = caseId == 9 ? JPH::Quat::sRotation(JPH::Vec3::sAxisZ(), 0.7f) : JPH::Quat::sIdentity();
    auto localAnchor = caseId == 7 ? JPH::Vec3(0.5f, 0, 0) : JPH::Vec3::sZero();
    auto fixed1 = JPH::RVec3(rotation * (JPH::Vec3(-1, height, 0) + localAnchor));
    auto fixed2 = JPH::RVec3(rotation * (JPH::Vec3(1, height, 0) + localAnchor));
    auto gravity = (caseId == 3 || caseId == 4 || caseId == 8) ? JPH::Vec3(0, -9.81f, 0) : JPH::Vec3::sZero();
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
    world.SetGravity(gravity);
    JPH::RefConst<JPH::SphereShape> sphere = new JPH::SphereShape(0.25f);
    JPH::BodyCreationSettings settings(sphere, JPH::RVec3::sZero(), JPH::Quat::sIdentity(), JPH::EMotionType::Dynamic, 0);
    settings.mAllowSleeping = false;
    settings.mLinearDamping = settings.mAngularDamping = 0;
    settings.mOverrideMassProperties = JPH::EOverrideMassProperties::MassAndInertiaProvided;
    settings.mMassPropertiesOverride.mMass = 2;
    settings.mMassPropertiesOverride.mInertia = JPH::Mat44::sScale(JPH::Vec3::sReplicate(0.2f));
    auto& bodies = world.GetBodyInterface();
    settings.mRotation = rotation;
    settings.mPosition = JPH::RVec3(rotation * JPH::Vec3(-1, 0, 0));
    auto* first = bodies.CreateBody(settings);
    settings.mMassPropertiesOverride.mMass = secondMass;
    settings.mPosition = JPH::RVec3(rotation * JPH::Vec3(1, 0, 0));
    auto* second = bodies.CreateBody(settings);
    if (!first || !second) return 3;
    bodies.AddBody(first->GetID(), JPH::EActivation::Activate);
    bodies.AddBody(second->GetID(), JPH::EActivation::Activate);
    JPH::PulleyConstraintSettings coupling;
    coupling.mSpace = JPH::EConstraintSpace::LocalToBodyCOM;
    coupling.mBodyPoint1 = coupling.mBodyPoint2 = JPH::RVec3(localAnchor);
    coupling.mFixedPoint1 = fixed1; coupling.mFixedPoint2 = fixed2;
    coupling.mRatio = ratio;
    if (caseId == 5) coupling.mMaxLength = 40;
    if (caseId == 8) coupling.mMinLength = coupling.mMaxLength = 400;
    JPH::Ref<JPH::PulleyConstraint> joint = new JPH::PulleyConstraint(*first, *second, coupling);
    world.AddConstraint(joint.GetPtr());
    if (caseId == 0 || caseId == 1 || caseId == 2 || caseId == 5 || caseId == 7 || caseId == 9)
        bodies.SetLinearVelocity(second->GetID(), rotation * JPH::Vec3(0, -1, 0));
    JPH::TempAllocatorImpl allocator(1024 * 1024);
    JPH::JobSystemSingleThreaded jobs(JPH::cMaxPhysicsJobs);
    for (int step = 1; step <= 360; ++step) {
        if (caseId == 6 && step == 181) joint->SetLength(0, 18);
        auto firstPoint = bodies.GetWorldTransform(first->GetID()) * JPH::RVec3(localAnchor);
        auto secondPoint = bodies.GetWorldTransform(second->GetID()) * JPH::RVec3(localAnchor);
        auto firstRadius = JPH::Vec3(firstPoint - bodies.GetCenterOfMassPosition(first->GetID()));
        auto secondRadius = JPH::Vec3(secondPoint - bodies.GetCenterOfMassPosition(second->GetID()));
        auto firstNormal = JPH::Vec3(firstPoint - fixed1).Normalized();
        auto secondNormal = JPH::Vec3(secondPoint - fixed2).Normalized();
        if (world.Update(1.0f / 60.0f, 1, &allocator, &jobs) != JPH::EPhysicsUpdateError::None) return 4;
        if (step == 1 || step % 15 == 0) {
            auto inverseRotation = rotation.Conjugated();
            float a = (inverseRotation * JPH::Vec3(bodies.GetPosition(first->GetID()))).GetY();
            float b = (inverseRotation * JPH::Vec3(bodies.GetPosition(second->GetID()))).GetY();
            auto va = bodies.GetLinearVelocity(first->GetID()); auto vb = bodies.GetLinearVelocity(second->GetID());
            auto wa = bodies.GetAngularVelocity(first->GetID()); auto wb = bodies.GetAngularVelocity(second->GetID());
            float lambda = joint->GetTotalLambdaPosition() * 60;
            auto force1 = firstNormal * lambda; auto force2 = secondNormal * (ratio * lambda);
            auto torque1 = inverseRotation * firstRadius.Cross(force1);
            auto torque2 = inverseRotation * secondRadius.Cross(force2);
            force1 = inverseRotation * force1; force2 = inverseRotation * force2;
            auto relative1 = inverseRotation * bodies.GetRotation(first->GetID());
            auto relative2 = inverseRotation * bodies.GetRotation(second->GetID());
            float angle1 = 2 * std::atan2(relative1.GetZ(), relative1.GetW());
            float angle2 = 2 * std::atan2(relative2.GetZ(), relative2.GetW());
            float length = JPH::Vec3(bodies.GetWorldTransform(first->GetID()) * JPH::RVec3(localAnchor) - fixed1).Length()
                + ratio * JPH::Vec3(bodies.GetWorldTransform(second->GetID()) * JPH::RVec3(localAnchor) - fixed2).Length();
            float energy = va.LengthSq() + 0.5f * secondMass * vb.LengthSq() + 0.1f * (wa.LengthSq() + wb.LengthSq());
            std::cout << "pulley " << caseId << ' ' << step << ' ' << a << ' ' << b << ' ' << (inverseRotation * va).GetY() << ' ' << (inverseRotation * vb).GetY()
                << ' ' << wa.GetZ() << ' ' << wb.GetZ() << ' ' << angle1 << ' ' << angle2 << ' ' << length
                << ' ' << force1.GetX() << ' ' << force1.GetY() << ' ' << force2.GetX() << ' ' << force2.GetY()
                << ' ' << torque1.GetZ() << ' ' << torque2.GetZ() << ' ' << energy << '\n';
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
    for (int caseId = 0; caseId < 10 && result == 0; ++caseId) result = Physics3D::runPulleyCase(caseId);
    JPH::UnregisterTypes();
    JPH::Factory::sInstance = nullptr;
    return result;
}
