#include <algorithm>
#include <array>
#include <cmath>
#include <cstdlib>
#include <iostream>
#include <memory>
#include <string>
#include <string_view>
#include <Jolt/Jolt.h>
#include <Jolt/ConfigurationString.h>
#include <Jolt/RegisterTypes.h>
#include <Jolt/Core/Factory.h>
#include <Jolt/Core/JobSystemSingleThreaded.h>
#include <Jolt/Core/TempAllocator.h>
#include <Jolt/Physics/PhysicsSystem.h>
#include <Jolt/Physics/Body/BodyCreationSettings.h>
#include <Jolt/Physics/Collision/BroadPhase/BroadPhaseLayerInterfaceTable.h>
#include <Jolt/Physics/Collision/BroadPhase/ObjectVsBroadPhaseLayerFilterTable.h>
#include <Jolt/Physics/Collision/ObjectLayerPairFilterTable.h>
#include <Jolt/Physics/Collision/CastResult.h>
#include <Jolt/Physics/Collision/RayCast.h>
#include <Jolt/Physics/Collision/Shape/BoxShape.h>
#include <Jolt/Physics/Collision/Shape/SphereShape.h>
#include <Jolt/Physics/Collision/Shape/HeightFieldShape.h>
#include <Jolt/Physics/Constraints/SixDOFConstraint.h>
#include <Jolt/Physics/Constraints/PulleyConstraint.h>
#include <Jolt/Physics/Constraints/PathConstraint.h>
#include <Jolt/Physics/Constraints/PathConstraintPathHermite.h>
#include <Jolt/Physics/Constraints/HingeConstraint.h>

namespace TerrainConstraints {

// -----------------------------------------------------------------------------

void emit(std::string_view name, float value) {
    if (!std::isfinite(value)) std::terminate();
    std::cout << name << '=' << value << '\n';
}

class World {
    private: JPH::BroadPhaseLayerInterfaceTable broadPhase { 2, 1 };
    private: JPH::ObjectLayerPairFilterTable pairFilter { 2 };
    private: std::unique_ptr<JPH::ObjectVsBroadPhaseLayerFilterTable> phaseFilter;
    public: JPH::PhysicsSystem physics;
    public: JPH::TempAllocatorImpl allocator { 2 * 1024 * 1024 };
    public: JPH::JobSystemSingleThreaded jobs { JPH::cMaxPhysicsJobs };
    public: explicit World(int positions = 8) {
        broadPhase.MapObjectToBroadPhaseLayer(0, JPH::BroadPhaseLayer(0));
        broadPhase.MapObjectToBroadPhaseLayer(1, JPH::BroadPhaseLayer(0));
        pairFilter.EnableCollision(0, 0);
        phaseFilter = std::make_unique<JPH::ObjectVsBroadPhaseLayerFilterTable>(broadPhase, 1, pairFilter, 2);
        physics.Init(32, 0, 64, 64, broadPhase, *phaseFilter, pairFilter);
        auto settings = physics.GetPhysicsSettings();
        settings.mNumVelocitySteps = 24;
        settings.mNumPositionSteps = positions;
        settings.mPenetrationSlop = 0.0005f;
        physics.SetPhysicsSettings(settings);
        physics.SetGravity(JPH::Vec3(0, -9.81f, 0));
    }
    public: JPH::Body* add(const JPH::Shape* shape, JPH::Vec3Arg position,
        float mass, bool fixed = false, JPH::ObjectLayer layer = 0) {
        JPH::BodyCreationSettings settings(shape, JPH::RVec3(position), JPH::Quat::sIdentity(),
            fixed ? JPH::EMotionType::Static : JPH::EMotionType::Dynamic, layer);
        settings.mAllowSleeping = false;
        settings.mFriction = settings.mRestitution = 0;
        settings.mLinearDamping = settings.mAngularDamping = 0;
        if (!fixed) {
            settings.mOverrideMassProperties = JPH::EOverrideMassProperties::MassAndInertiaProvided;
            settings.mMassPropertiesOverride.mMass = mass;
            settings.mMassPropertiesOverride.mInertia = JPH::Mat44::sScale(JPH::Vec3::sReplicate(mass * 0.1f));
        }
        auto& bodies = physics.GetBodyInterface();
        auto* body = bodies.CreateBody(settings);
        if (!body) std::terminate();
        bodies.AddBody(body->GetID(), fixed ? JPH::EActivation::DontActivate : JPH::EActivation::Activate);
        return body;
    }
    public: void step() {
        if (physics.Update(1.0f / 60.0f, 1, &allocator, &jobs) != JPH::EPhysicsUpdateError::None) std::terminate();
    }
};

// -----------------------------------------------------------------------------

void terrainSample(JPH::HeightFieldShape& shape, std::string_view label, float x, float z) {
    const JPH::RayCast ray(JPH::Vec3(x * 0.75f, 2, z * 1.25f), JPH::Vec3(0, -4, 0));
    JPH::RayCastResult hit;
    if (!shape.CastRay(ray, JPH::SubShapeIDCreator(), hit)) std::terminate();
    const auto point = ray.GetPointOnRay(hit.mFraction);
    emit(label, point.GetY());
    const auto normal = shape.GetSurfaceNormal(hit.mSubShapeID2, point);
    emit(std::string(label) + "_nx", normal.GetX());
    emit(std::string(label) + "_ny", normal.GetY());
    emit(std::string(label) + "_nz", normal.GetZ());
    emit(std::string(label) + "_fraction", hit.mFraction);
}

void terrainVersions() {
    std::array<float, 64> heights;
    for (int index = 0; index < 64; ++index) heights[index] = 0.02f * (index % 8) - 0.03f * (index / 8);
    JPH::HeightFieldShapeSettings settings(heights.data(), JPH::Vec3::sZero(), JPH::Vec3(0.75f, 1, 1.25f), 8);
    settings.mBitsPerSample = 16;
    settings.mBlockSize = 2;
    settings.mMinHeightValue = -0.5f;
    settings.mMaxHeightValue = 0.8f;
    auto result = settings.Create();
    if (result.HasError()) std::terminate();
    JPH::Ref<JPH::HeightFieldShape> shape = static_cast<JPH::HeightFieldShape*>(result.Get().GetPtr());
    JPH::TempAllocatorImpl allocator(2 * 1024 * 1024);
    terrainSample(*shape, "terrain_before", 2.25f, 2.4f);
    const std::array<float, 4> raised { 0.4f, 0.4f, 0.4f, 0.4f };
    shape->SetHeights(2, 2, 2, 2, raised.data(), 2, allocator);
    terrainSample(*shape, "terrain_raised", 2.25f, 2.4f);
    terrainSample(*shape, "terrain_outside", 6.1f, 3.7f);
    const float hole = JPH::HeightFieldShapeConstants::cNoCollisionValue;
    const std::array<float, 4> holes { hole, hole, hole, hole };
    shape->SetHeights(4, 4, 2, 2, holes.data(), 2, allocator);
    JPH::RayCastResult missing;
    const bool hit = shape->CastRay(JPH::RayCast(JPH::Vec3(4.4f * 0.75f, 2, 4.3f * 1.25f), JPH::Vec3(0, -4, 0)), JPH::SubShapeIDCreator(), missing);
    emit("terrain_hole", hit ? 1.0f : 0.0f);
    const std::array<float, 4> restored { heights[36], heights[37], heights[44], heights[45] };
    shape->SetHeights(4, 4, 2, 2, restored.data(), 2, allocator);
    terrainSample(*shape, "terrain_restored", 4.4f, 4.3f);
}

// -----------------------------------------------------------------------------

JPH::Ref<JPH::SixDOFConstraint> guide(World& world, JPH::Body& anchor, JPH::Body& body, float x) {
    JPH::SixDOFConstraintSettings settings;
    settings.mSpace = JPH::EConstraintSpace::LocalToBodyCOM;
    settings.mPosition1 = JPH::RVec3(x, 2, 0);
    settings.mPosition2 = JPH::RVec3::sZero();
    using Axis = JPH::SixDOFConstraintSettings::EAxis;
    settings.MakeFixedAxis(Axis::TranslationX);
    settings.MakeFixedAxis(Axis::TranslationZ);
    settings.MakeFixedAxis(Axis::RotationX);
    settings.MakeFixedAxis(Axis::RotationY);
    settings.MakeFixedAxis(Axis::RotationZ);
    JPH::Ref<JPH::SixDOFConstraint> joint = new JPH::SixDOFConstraint(anchor, body, settings);
    world.physics.AddConstraint(joint.GetPtr());
    return joint;
}

void pulleyGuides(int caseId) {
    const int positions = caseId == 1 ? 48 : 8;
    emit("pulley_" + std::to_string(caseId) + "_positions", static_cast<float>(positions));
    World world(positions);
    auto* floor = world.add(new JPH::BoxShape(JPH::Vec3(10, 0.25f, 10), 0), JPH::Vec3(0, -0.25f, 0), 0, true);
    auto* anchor = world.add(new JPH::SphereShape(0.1f), JPH::Vec3::sZero(), 0, true, 1);
    auto* first = world.add(new JPH::BoxShape(JPH::Vec3::sReplicate(0.25f), 0), JPH::Vec3(-1, 2, 0), 2);
    auto* second = world.add(new JPH::BoxShape(JPH::Vec3::sReplicate(0.25f), 0), JPH::Vec3(1, 2, 0), 8);
    auto left = guide(world, *anchor, *first, -1);
    auto right = guide(world, *anchor, *second, 1);
    const float ratio = caseId == 1 ? 2.0f : 1.0f;
    const float z1 = caseId == 1 ? 0.4f : 0.0f;
    const float z2 = caseId == 1 ? -0.6f : 0.0f;
    const float length = std::sqrt(36 + z1 * z1) + ratio * std::sqrt(36 + z2 * z2);
    JPH::PulleyConstraintSettings settings;
    settings.mSpace = JPH::EConstraintSpace::LocalToBodyCOM;
    settings.mBodyPoint1 = settings.mBodyPoint2 = JPH::RVec3::sZero();
    settings.mFixedPoint1 = JPH::RVec3(-1, 8, z1);
    settings.mFixedPoint2 = JPH::RVec3(1, 8, z2);
    settings.mRatio = ratio;
    settings.mMinLength = settings.mMaxLength = length;
    JPH::Ref<JPH::PulleyConstraint> joint = new JPH::PulleyConstraint(*first, *second, settings);
    world.physics.AddConstraint(joint.GetPtr());
    float maximumError = 0;
    bool contacts = false;
    const std::string prefix = "pulley_" + std::to_string(caseId) + "_";
    for (int step = 1; step <= 360; ++step) {
        world.step();
        if (step == 1) {
            emit(prefix + "first_vy", first->GetLinearVelocity().GetY());
            emit(prefix + "second_vy", second->GetLinearVelocity().GetY());
        }
        const auto p1 = JPH::Vec3(first->GetPosition());
        const auto p2 = JPH::Vec3(second->GetPosition());
        const float actual = (p1 - JPH::Vec3(-1, 8, z1)).Length() + ratio * (p2 - JPH::Vec3(1, 8, z2)).Length();
        maximumError = std::max(maximumError, std::abs(actual - length));
        maximumError = std::max(maximumError, std::abs(p1.GetX() + 1));
        maximumError = std::max(maximumError, std::abs(p2.GetX() - 1));
        maximumError = std::max(maximumError, std::abs(p1.GetZ()));
        maximumError = std::max(maximumError, std::abs(p2.GetZ()));
        contacts |= world.physics.WereBodiesInContact(floor->GetID(), second->GetID());
    }
    if (!contacts) std::terminate();
    emit(prefix + "first_y", static_cast<float>(first->GetPosition().GetY()));
    emit(prefix + "second_y", static_cast<float>(second->GetPosition().GetY()));
    emit(prefix + "tension", std::abs(joint->GetTotalLambdaPosition()) * 60);
    emit(prefix + "final_first_vy", first->GetLinearVelocity().GetY());
    emit(prefix + "final_second_vy", second->GetLinearVelocity().GetY());
    emit(prefix + "guide_first_z", left->GetTotalLambdaPosition().GetZ() * 60);
    emit(prefix + "guide_second_z", right->GetTotalLambdaPosition().GetZ() * 60);
    emit(prefix + "max_error", maximumError);
    joint->SetEnabled(false);
    // Jolt removal is explicit; Silex additionally invalidates incident handles.
    world.physics.RemoveConstraint(joint.GetPtr());
    world.physics.RemoveConstraint(right.GetPtr());
    const auto id = second->GetID();
    world.physics.GetBodyInterface().RemoveBody(id);
    world.physics.GetBodyInterface().DestroyBody(id);
    world.step();
    const auto& bodies = world.physics.GetBodyInterface();
    emit(prefix + "lifetime", !bodies.IsAdded(id) && bodies.IsAdded(first->GetID()) && bodies.IsAdded(floor->GetID()) ? 1.0f : 0.0f);
}

// -----------------------------------------------------------------------------

void loadedPath() {
    World world;
    auto* rail = world.add(new JPH::SphereShape(0.1f), JPH::Vec3(0, 3, 0), 0, true, 1);
    auto* carrier = world.add(new JPH::SphereShape(0.2f), JPH::Vec3(0, 3, 0), 2);
    auto* payload = world.add(new JPH::SphereShape(0.2f), JPH::Vec3(0, 2.2f, 0), 4);
    auto* wall = world.add(new JPH::BoxShape(JPH::Vec3(0.2f, 2, 2), 0), JPH::Vec3(1.7f, 2, 0), 0, true);
    JPH::Ref<JPH::PathConstraintPathHermite> path = new JPH::PathConstraintPathHermite;
    path->AddPoint(JPH::Vec3(-2, 0, 0), JPH::Vec3(4, 0, 0), JPH::Vec3::sAxisY());
    path->AddPoint(JPH::Vec3(2, 0, 0), JPH::Vec3(4, 0, 0), JPH::Vec3::sAxisY());
    JPH::PathConstraintSettings pathSettings;
    pathSettings.mPath = path;
    pathSettings.mPathFraction = 0.5f;
    pathSettings.mRotationConstraintType = JPH::EPathRotationConstraintType::FullyConstrained;
    pathSettings.mPositionMotorSettings.mMinForceLimit = -20;
    pathSettings.mPositionMotorSettings.mMaxForceLimit = 20;
    JPH::Ref<JPH::PathConstraint> follower = new JPH::PathConstraint(*rail, *carrier, pathSettings);
    world.physics.AddConstraint(follower.GetPtr());
    follower->SetPositionMotorState(JPH::EMotorState::Velocity);
    follower->SetTargetVelocity(0.5f);
    const auto axis = JPH::Vec3(0.3f, 0.2f, 1).Normalized();
    const auto normal = axis.Cross(JPH::Vec3::sAxisY()).Normalized();
    JPH::HingeConstraintSettings hingeSettings;
    hingeSettings.mSpace = JPH::EConstraintSpace::LocalToBodyCOM;
    hingeSettings.mPoint1 = JPH::RVec3::sZero();
    hingeSettings.mPoint2 = JPH::RVec3(0, 0.8f, 0);
    hingeSettings.mHingeAxis1 = hingeSettings.mHingeAxis2 = axis;
    hingeSettings.mNormalAxis1 = hingeSettings.mNormalAxis2 = normal;
    JPH::Ref<JPH::HingeConstraint> hinge = new JPH::HingeConstraint(*carrier, *payload, hingeSettings);
    world.physics.AddConstraint(hinge.GetPtr());
    float maximumError = 0;
    float maximumMotor = 0;
    float maximumNormalError = 0;
    float averageSupport = 0;
    bool contacts = false;
    for (int step = 1; step <= 360; ++step) {
        world.step();
        const auto first = carrier->GetWorldTransform() * JPH::RVec3(hinge->GetLocalSpacePoint1());
        const auto second = payload->GetWorldTransform() * JPH::RVec3(hinge->GetLocalSpacePoint2());
        maximumError = std::max(maximumError, JPH::Vec3(second - first).Length());
        maximumNormalError = std::max(maximumNormalError, std::max(std::abs(static_cast<float>(carrier->GetPosition().GetY()) - 3), std::abs(static_cast<float>(carrier->GetPosition().GetZ()))));
        maximumMotor = std::max(maximumMotor, std::abs(follower->GetTotalLambdaMotor()) * 60);
        if (step > 300) averageSupport += follower->GetTotalLambdaPosition()[0];
        contacts |= world.physics.WereBodiesInContact(carrier->GetID(), wall->GetID());
    }
    if (!contacts) std::terminate();
    emit("path_blocked_x", static_cast<float>(carrier->GetPosition().GetX()));
    emit("path_support_y", averageSupport);
    emit("path_normal_error", maximumNormalError);
    emit("path_max_error", maximumError);
    emit("path_max_motor", maximumMotor);
    follower->SetTargetVelocity(-0.5f);
    for (int step = 0; step < 120; ++step) world.step();
    emit("path_released", carrier->GetPosition().GetX() < 1.2f ? 1.0f : 0.0f);
    world.physics.RemoveConstraint(follower.GetPtr());
    world.physics.RemoveConstraint(hinge.GetPtr());
    const auto id = carrier->GetID();
    world.physics.GetBodyInterface().RemoveBody(id);
    world.physics.GetBodyInterface().DestroyBody(id);
    world.step();
    const auto& bodies = world.physics.GetBodyInterface();
    emit("path_lifetime", !bodies.IsAdded(id) && bodies.IsAdded(payload->GetID()) && bodies.IsAdded(rail->GetID()) ? 1.0f : 0.0f);
}

// -----------------------------------------------------------------------------

} // namespace TerrainConstraints

int main(int count, char** values) {
    if (count == 2 && std::string_view(values[1]) == "--configuration") {
        std::cout << JPH::GetConfigurationString() << '\n'; return 0;
    }
    if (count != 1) return 2;
    JPH::RegisterDefaultAllocator();
    auto factory = std::make_unique<JPH::Factory>();
    JPH::Factory::sInstance = factory.get();
    JPH::RegisterTypes();
    std::cout.precision(9);
    TerrainConstraints::terrainVersions();
    TerrainConstraints::pulleyGuides(0);
    TerrainConstraints::pulleyGuides(1);
    TerrainConstraints::loadedPath();
    JPH::UnregisterTypes();
    JPH::Factory::sInstance = nullptr;
}
