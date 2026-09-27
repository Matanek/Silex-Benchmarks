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
#include <numbers>
#include <string_view>

namespace Physics3D {

// -----------------------------------------------------------------------------

struct Fixture {
    int radius;
    int mass;
    std::array<int, 3> position;
    std::array<int, 3> velocity;
    int steps;
    int stepMillis;
};

// -----------------------------------------------------------------------------

bool parsePositive(const char* text, int& value, bool allowZero = false) {
    const auto* end = text + std::char_traits<char>::length(text);
    const auto parsed = std::from_chars(text, end, value);
    return parsed.ec == std::errc{} && parsed.ptr == end &&
        (value > 0 || (allowZero && value == 0));
}

bool parseFixture(int count, char** values, Fixture& fixture) {
    if (count != 11) return false;
    std::array<int*, 10> fields {
        &fixture.radius, &fixture.mass,
        &fixture.position[0], &fixture.position[1], &fixture.position[2],
        &fixture.velocity[0], &fixture.velocity[1], &fixture.velocity[2],
        &fixture.steps, &fixture.stepMillis
    };
    for (std::size_t index = 0; index < fields.size(); ++index) {
        if (!parsePositive(values[index + 1], *fields[index], index >= 2 && index <= 7)) {
            return false;
        }
    }
    return true;
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

    const auto radius = static_cast<float>(fixture.radius);
    JPH::RefConst<JPH::SphereShape> sphere = new JPH::SphereShape(radius);
    auto properties = sphere->GetMassProperties();
    properties.ScaleToMass(static_cast<float>(fixture.mass));
    const auto inertia = properties.mInertia.GetColumn3(0).GetX();

    const auto rotation = JPH::Quat::sRotation(
        JPH::Vec3::sAxisY(), std::numbers::pi_v<float> * 0.5f
    );
    const auto rotated = rotation * JPH::Vec3::sAxisX();
    JPH::BodyCreationSettings settings(
        sphere,
        JPH::RVec3(
            fixture.position[0], fixture.position[1], fixture.position[2]
        ),
        rotation,
        JPH::EMotionType::Dynamic,
        0
    );
    settings.mLinearDamping = 0.0f;
    settings.mAngularDamping = 0.0f;
    settings.mGravityFactor = 0.0f;
    settings.mOverrideMassProperties = JPH::EOverrideMassProperties::MassAndInertiaProvided;
    settings.mMassPropertiesOverride = properties;

    auto& bodies = world.GetBodyInterface();
    const auto id = bodies.CreateAndAddBody(settings, JPH::EActivation::Activate);
    if (id.IsInvalid()) return 3;
    bodies.SetLinearVelocity(id, JPH::Vec3(
        fixture.velocity[0], fixture.velocity[1], fixture.velocity[2]
    ));

    JPH::TempAllocatorImpl allocator(1024 * 1024);
    JPH::JobSystemSingleThreaded jobs(JPH::cMaxPhysicsJobs);
    const auto dt = static_cast<float>(fixture.stepMillis) / 1000.0f;
    for (int step = 0; step < fixture.steps; ++step) {
        if (world.Update(dt, 1, &allocator, &jobs) != JPH::EPhysicsUpdateError::None) return 4;
    }
    const auto position = bodies.GetCenterOfMassPosition(id);
    const auto velocity = bodies.GetLinearVelocity(id);

    std::cout.precision(9);
    std::cout << "position_x=" << position.GetX() << '\n'
              << "position_y=" << position.GetY() << '\n'
              << "position_z=" << position.GetZ() << '\n'
              << "velocity_x=" << velocity.GetX() << '\n'
              << "velocity_y=" << velocity.GetY() << '\n'
              << "velocity_z=" << velocity.GetZ() << '\n'
              << "rotated_x=" << rotated.GetX() << '\n'
              << "rotated_y=" << rotated.GetY() << '\n'
              << "rotated_z=" << rotated.GetZ() << '\n'
              << "inertia_x=" << inertia << '\n';

    bodies.RemoveBody(id);
    bodies.DestroyBody(id);
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
        std::cerr << "invalid physics3d fixture arguments\n";
        return 2;
    }
    return Physics3D::run(fixture);
}
