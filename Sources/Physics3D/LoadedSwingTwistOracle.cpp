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
#include <Jolt/Physics/Constraints/SwingTwistConstraint.h>

namespace Physics3D {

// -----------------------------------------------------------------------------

void writeVector(JPH::Vec3Arg value) {
    std::cout << ' ' << value.GetX() << ' ' << value.GetY() << ' ' << value.GetZ();
}

void writeQuaternion(JPH::QuatArg value) {
    std::cout << ' ' << value.GetX() << ' ' << value.GetY() << ' ' << value.GetZ() << ' ' << value.GetW();
}

JPH::Quat swingTarget(float direction) {
    const float y = 0.1f * direction;
    const float z = -0.075f * direction;
    const auto swing = JPH::Quat(0, std::sin(y) * std::cos(z), std::cos(y) * std::sin(z), std::cos(y) * std::cos(z)).Normalized();
    return swing * JPH::Quat::sRotation(JPH::Vec3::sAxisX(), 0.25f * direction);
}

// -----------------------------------------------------------------------------

int runLoadedSwing(int mass, int rate, int side) {
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
    world.SetGravity(JPH::Vec3(0, -9.81f, 0));
    JPH::RefConst<JPH::SphereShape> shape = new JPH::SphereShape(0.25f);
    const auto base = JPH::Quat::sRotation(JPH::Vec3(1, 2, -1).Normalized(), 0.7f);
    const auto frame = JPH::Quat::sRotation(JPH::Vec3::sAxisZ(), 0.35f);
    const JPH::Vec3 lever(0.5f, 0.2f, 0.4f * side);
    JPH::BodyCreationSettings supportSettings(shape, JPH::RVec3::sZero(), base, JPH::EMotionType::Static, 0);
    JPH::BodyCreationSettings bodySettings(shape, JPH::RVec3(base * lever), base, JPH::EMotionType::Dynamic, 0);
    bodySettings.mAllowSleeping = false;
    bodySettings.mLinearDamping = bodySettings.mAngularDamping = 0;
    bodySettings.mOverrideMassProperties = JPH::EOverrideMassProperties::MassAndInertiaProvided;
    bodySettings.mMassPropertiesOverride.mMass = static_cast<float>(mass);
    bodySettings.mMassPropertiesOverride.mInertia = JPH::Mat44::sScale(JPH::Vec3::sReplicate(0.4f));
    auto& bodies = world.GetBodyInterface();
    auto* support = bodies.CreateBody(supportSettings);
    auto* body = bodies.CreateBody(bodySettings);
    if (!support || !body) return 3;
    bodies.AddBody(support->GetID(), JPH::EActivation::DontActivate);
    bodies.AddBody(body->GetID(), JPH::EActivation::Activate);
    JPH::SwingTwistConstraintSettings settings;
    settings.mSpace = JPH::EConstraintSpace::LocalToBodyCOM;
    settings.mPosition1 = JPH::RVec3::sZero();
    settings.mPosition2 = JPH::RVec3(-lever);
    settings.mTwistAxis1 = settings.mTwistAxis2 = frame * JPH::Vec3::sAxisX();
    settings.mPlaneAxis1 = settings.mPlaneAxis2 = frame * JPH::Vec3::sAxisZ();
    settings.mPlaneHalfConeAngle = settings.mNormalHalfConeAngle = 0.8f;
    settings.mTwistMinAngle = -0.8f;
    settings.mTwistMaxAngle = 0.8f;
    for (auto* motor : { &settings.mTwistMotorSettings, &settings.mSwingMotorSettings }) {
        motor->mMinTorqueLimit = -30;
        motor->mMaxTorqueLimit = 30;
        motor->mSpringSettings = JPH::SpringSettings(JPH::ESpringMode::StiffnessAndDamping, 80, 15);
    }
    JPH::Ref<JPH::SwingTwistConstraint> joint = new JPH::SwingTwistConstraint(*support, *body, settings);
    joint->SetTwistMotorState(JPH::EMotorState::Position);
    joint->SetSwingMotorState(JPH::EMotorState::Position);
    world.AddConstraint(joint.GetPtr());
    JPH::TempAllocatorImpl allocator(1024 * 1024);
    JPH::JobSystemSingleThreaded jobs(JPH::cMaxPhysicsJobs);
    const float delta = 1.0f / rate;
    for (int step = 1; step <= rate * 9; ++step) {
        if (step == 1 || step == rate * 3 + 1 || step == rate * 6 + 1) {
            float direction = static_cast<float>(side);
            if (step > rate * 3) direction = -direction;
            if (step > rate * 6) direction = 0;
            joint->SetTargetOrientationCS(swingTarget(direction));
            joint->ResetWarmStart();
        }
        const auto beforePosition = JPH::Vec3(bodies.GetPosition(body->GetID()));
        const auto beforeRotation = bodies.GetRotation(body->GetID());
        const auto beforeVelocity = bodies.GetLinearVelocity(body->GetID());
        const auto beforeAngular = bodies.GetAngularVelocity(body->GetID());
        if (world.Update(delta, 1, &allocator, &jobs) != JPH::EPhysicsUpdateError::None) return 4;
        if (joint->GetTotalLambdaTwist() != 0 || joint->GetTotalLambdaSwingY() != 0 || joint->GetTotalLambdaSwingZ() != 0) return 5;
        const auto position = JPH::Vec3(bodies.GetPosition(body->GetID()));
        const auto rotation = bodies.GetRotation(body->GetID());
        const auto motor = joint->GetTotalLambdaMotor() / delta;
        const auto torque = (beforeRotation * frame) * motor;
        const auto angular = bodies.GetAngularVelocity(body->GetID());
        std::cout << "loadedswing " << mass << ' ' << rate << ' ' << side << ' ' << step;
        writeVector(beforePosition); writeQuaternion(beforeRotation); writeVector(beforeVelocity); writeVector(beforeAngular);
        writeVector(position); writeQuaternion(rotation); writeVector(bodies.GetLinearVelocity(body->GetID())); writeVector(angular);
        writeVector(joint->GetTotalLambdaPosition() / delta); writeVector(torque); writeVector(motor);
        writeQuaternion(joint->GetRotationInConstraintSpace()); writeVector((rotation * frame).Conjugated() * angular);
        writeVector(position - rotation * lever);
        std::cout << '\n';
    }
    world.RemoveConstraint(joint.GetPtr());
    bodies.RemoveBody(support->GetID()); bodies.RemoveBody(body->GetID());
    bodies.DestroyBody(support->GetID()); bodies.DestroyBody(body->GetID());
    return 0;
}

// -----------------------------------------------------------------------------

} // namespace Physics3D

int main() {
#ifdef JPH_ENABLE_ASSERTS
    JPH::AssertFailed = [](const char* expression, const char* message, const char* file, JPH::uint line) {
        std::cerr << "Jolt assertion: " << expression << " at " << file << ':' << line << " message=" << (message ? message : "") << '\n';
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
    for (int mass : { 1, 2 }) for (int rate : { 60, 120 }) for (int side : { -1, 1 }) {
        if (result == 0) result = Physics3D::runLoadedSwing(mass, rate, side);
    }
    JPH::UnregisterTypes();
    JPH::Factory::sInstance = nullptr;
    return result;
}
