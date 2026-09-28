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
#include <Jolt/Physics/Collision/Shape/SphereShape.h>
#include <array>
#include <charconv>
#include <iostream>
#include <string_view>

namespace Physics3D {

// -----------------------------------------------------------------------------

struct Fixture {
    int radiusMillimeters;
    int centerMillimeters;
    int speedMillimetersPerSecond;
    int stepMilliseconds;
    int restitutionPermille;
};

// -----------------------------------------------------------------------------

bool parsePositive(const char* text, int& value, bool allowZero = false) {
    const auto* end = text + std::char_traits<char>::length(text);
    const auto parsed = std::from_chars(text, end, value);
    return parsed.ec == std::errc{} && parsed.ptr == end &&
        (value > 0 || (allowZero && value == 0));
}

bool parseFixture(int count, char** values, Fixture& fixture) {
    if (count != 6) return false;
    std::array<int*, 5> fields {
        &fixture.radiusMillimeters, &fixture.centerMillimeters,
        &fixture.speedMillimetersPerSecond, &fixture.stepMilliseconds,
        &fixture.restitutionPermille
    };
    for (std::size_t index = 0; index < fields.size(); ++index) {
        if (!parsePositive(values[index + 1], *fields[index], index == 4)) return false;
    }
    return fixture.restitutionPermille <= 1000;
}

// -----------------------------------------------------------------------------

int run(const Fixture& fixture) {
    JPH::RegisterDefaultAllocator();
    JPH::Factory::sInstance = new JPH::Factory();
    JPH::RegisterTypes();

    JPH::BroadPhaseLayerInterfaceTable broadPhase(1, 1);
    broadPhase.MapObjectToBroadPhaseLayer(0, JPH::BroadPhaseLayer(0));
    JPH::ObjectLayerPairFilterTable pairFilter(1);
    pairFilter.EnableCollision(0, 0);
    JPH::ObjectVsBroadPhaseLayerFilterTable phaseFilter(broadPhase, 1, pairFilter, 1);

    JPH::PhysicsSystem world;
    world.Init(16, 0, 16, 16, broadPhase, phaseFilter, pairFilter);
    world.SetGravity(JPH::Vec3::sZero());

    const auto radius = fixture.radiusMillimeters / 1000.0f;
    const auto center = fixture.centerMillimeters / 1000.0f;
    const auto speed = fixture.speedMillimetersPerSecond / 1000.0f;
    const auto delta = fixture.stepMilliseconds / 1000.0f;
    const auto restitution = fixture.restitutionPermille / 1000.0f;
    JPH::RefConst<JPH::SphereShape> sphere = new JPH::SphereShape(radius);
    JPH::BodyCreationSettings firstSettings(
        sphere, JPH::RVec3(-center, 0.0, 0.0), JPH::Quat::sIdentity(),
        JPH::EMotionType::Dynamic, 0
    );
    JPH::BodyCreationSettings secondSettings(
        sphere, JPH::RVec3(center, 0.0, 0.0), JPH::Quat::sIdentity(),
        JPH::EMotionType::Dynamic, 0
    );
    firstSettings.mLinearDamping = 0.0f;
    secondSettings.mLinearDamping = 0.0f;
    firstSettings.mAngularDamping = 0.0f;
    secondSettings.mAngularDamping = 0.0f;
    firstSettings.mFriction = 0.0f;
    secondSettings.mFriction = 0.0f;
    firstSettings.mRestitution = restitution;
    secondSettings.mRestitution = restitution;

    auto& bodies = world.GetBodyInterface();
    const auto first = bodies.CreateAndAddBody(firstSettings, JPH::EActivation::Activate);
    const auto second = bodies.CreateAndAddBody(secondSettings, JPH::EActivation::Activate);
    if (first.IsInvalid() || second.IsInvalid()) return 3;
    bodies.SetLinearVelocity(first, JPH::Vec3(speed, 0.0, 0.0));
    bodies.SetLinearVelocity(second, JPH::Vec3(-speed, 0.0, 0.0));

    JPH::TempAllocatorImpl allocator(1024 * 1024);
    JPH::JobSystemSingleThreaded jobs(JPH::cMaxPhysicsJobs);
    if (world.Update(delta, 1, &allocator, &jobs) != JPH::EPhysicsUpdateError::None) return 4;

    std::cout.precision(9);
    std::cout << "first_x=" << bodies.GetCenterOfMassPosition(first).GetX() << '\n'
              << "second_x=" << bodies.GetCenterOfMassPosition(second).GetX() << '\n'
              << "first_vx=" << bodies.GetLinearVelocity(first).GetX() << '\n'
              << "second_vx=" << bodies.GetLinearVelocity(second).GetX() << '\n';

    bodies.RemoveBody(first);
    bodies.RemoveBody(second);
    bodies.DestroyBody(first);
    bodies.DestroyBody(second);
    JPH::UnregisterTypes();
    delete JPH::Factory::sInstance;
    JPH::Factory::sInstance = nullptr;
    return 0;
}

} // namespace Physics3D

int main(int count, char** values) {
    if (count == 2 && std::string_view(values[1]) == "--configuration") {
        std::cout << JPH::GetConfigurationString() << '\n';
        return 0;
    }
    Physics3D::Fixture fixture {};
    if (!Physics3D::parseFixture(count, values, fixture)) {
        std::cerr << "invalid physics3d contact fixture arguments\n";
        return 2;
    }
    return Physics3D::run(fixture);
}
