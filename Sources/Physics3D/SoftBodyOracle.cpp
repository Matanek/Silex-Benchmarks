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
#include <Jolt/Physics/SoftBody/SoftBodyCreationSettings.h>
#include <Jolt/Physics/SoftBody/SoftBodyMotionProperties.h>
#include <Jolt/Physics/Collision/Shape/PlaneShape.h>
#include <Jolt/Physics/Collision/Shape/SphereShape.h>
#include <Jolt/Physics/Collision/Shape/ConvexHullShape.h>
#include <Jolt/Physics/Collision/Shape/TriangleShape.h>
#include <Jolt/Physics/Collision/Shape/MeshShape.h>
#include <algorithm>
#include <array>
#include <iostream>
#include <string_view>

namespace Physics3D {

// -----------------------------------------------------------------------------

class Registration {
    public: Registration() {
        JPH::RegisterDefaultAllocator();
        JPH::Factory::sInstance = new JPH::Factory();
        JPH::RegisterTypes();
    }
    public: ~Registration() {
        JPH::UnregisterTypes();
        delete JPH::Factory::sInstance;
        JPH::Factory::sInstance = nullptr;
    }
    public: Registration(const Registration&) = delete;
    public: Registration& operator=(const Registration&) = delete;
};

// -----------------------------------------------------------------------------

JPH::Ref<JPH::SoftBodySharedSettings> makeDefinition(std::string_view scenario) {
    using Settings = JPH::SoftBodySharedSettings;
    JPH::Ref<Settings> settings = new Settings();
    if (scenario == "edge") {
        settings->mVertices.emplace_back(JPH::Float3(0, 0, 0), JPH::Float3(0, 0, 0), 0);
        settings->mVertices.emplace_back(JPH::Float3(1, 0, 0), JPH::Float3(1, 0, 0), 1);
        settings->mEdgeConstraints.emplace_back(0, 1, 0.001f);
        settings->CalculateEdgeLengths();
    } else if (scenario == "volume" || scenario == "pressure") {
        settings->mVertices.emplace_back(JPH::Float3(0, 0, 0));
        settings->mVertices.emplace_back(JPH::Float3(1, 0, 0));
        settings->mVertices.emplace_back(JPH::Float3(0, 1, 0));
        settings->mVertices.emplace_back(JPH::Float3(0, 0, 1), JPH::Float3(0, 0, 0.6f));
        settings->mFaces.emplace_back(0, 2, 1);
        settings->mFaces.emplace_back(0, 1, 3);
        settings->mFaces.emplace_back(0, 3, 2);
        settings->mFaces.emplace_back(1, 2, 3);
        if (scenario == "volume") {
            settings->mVolumeConstraints.emplace_back(0, 1, 2, 3, 0.001f);
            settings->CalculateVolumeConstraintVolumes();
        }
    } else if (scenario == "bend") {
        settings->mVertices.emplace_back(JPH::Float3(0, 0, 0));
        settings->mVertices.emplace_back(JPH::Float3(1, 0, 0));
        settings->mVertices.emplace_back(JPH::Float3(0, 1, 0));
        settings->mVertices.emplace_back(JPH::Float3(0, -1, 0), JPH::Float3(0, 0, 0.6f));
        settings->mDihedralBendConstraints.emplace_back(0, 1, 2, 3, 0.001f);
        settings->CalculateBendConstraintConstants();
    } else if (scenario == "tether") {
        settings->mVertices.emplace_back(JPH::Float3(0, 0, 0), JPH::Float3(0, 0, 0), 0);
        settings->mVertices.emplace_back(JPH::Float3(1, 0, 0), JPH::Float3(1, 0, 0), 1);
        settings->mLRAConstraints.emplace_back(0, 1, 1.1f);
    } else if (scenario == "convex-contact") {
        settings->mVertices.emplace_back(JPH::Float3(0.4f, 0, 0));
    } else if (scenario == "triangle-contact" || scenario == "mesh-contact") {
        settings->mVertices.emplace_back(JPH::Float3(0, -0.08f, 0));
        settings->mVertices.emplace_back(JPH::Float3(0, 0.2f, 0), JPH::Float3(0, 0, 0), 0);
    } else if (scenario == "front-sweep" || scenario == "back-sweep") {
        const float sign = scenario == "front-sweep" ? 1.0f : -1.0f;
        settings->mVertices.emplace_back(JPH::Float3(0, sign, 0), JPH::Float3(0, -120*sign, 0));
    } else {
        return nullptr;
    }
    settings->Optimize();
    return settings;
}

// -----------------------------------------------------------------------------

JPH::Ref<JPH::SoftBodySharedSettings> makeSurface(std::string_view scenario) {
    using Settings = JPH::SoftBodySharedSettings;
    JPH::Ref<Settings> settings = new Settings();
    if (scenario == "cube") {
        const std::array<JPH::Float3, 8> positions {
            JPH::Float3(-0.5f, -0.5f, -0.5f), JPH::Float3(0.5f, -0.5f, -0.5f),
            JPH::Float3(0.5f, 0.5f, -0.5f), JPH::Float3(-0.5f, 0.5f, -0.5f),
            JPH::Float3(-0.5f, -0.5f, 0.5f), JPH::Float3(0.5f, -0.5f, 0.5f),
            JPH::Float3(0.5f, 0.5f, 0.5f), JPH::Float3(-0.5f, 0.5f, 0.5f)
        };
        for (const auto& position : positions) settings->mVertices.emplace_back(position, JPH::Float3(1, -3, 0), 8);
        constexpr std::array<int, 36> faces { 0,2,1,0,3,2,4,5,6,4,6,7,0,1,5,0,5,4,3,7,6,3,6,2,0,4,7,0,7,3,1,2,6,1,6,5 };
        for (int i = 0; i < 36; i += 3) settings->mFaces.emplace_back(faces[i], faces[i+1], faces[i+2]);
        constexpr std::array<int, 24> tetrahedra { 0,1,2,6,0,2,3,6,0,3,7,6,0,7,4,6,0,4,5,6,0,5,1,6 };
        for (int i = 0; i < 24; i += 4) {
            settings->mVolumeConstraints.emplace_back(tetrahedra[i], tetrahedra[i+1], tetrahedra[i+2], tetrahedra[i+3]);
            for (int a = 0; a < 4; ++a) for (int b = a+1; b < 4; ++b) {
                const auto first = tetrahedra[i+a];
                const auto second = tetrahedra[i+b];
                bool found = false;
                for (const auto& edge : settings->mEdgeConstraints) {
                    if ((edge.mVertex[0] == first && edge.mVertex[1] == second) ||
                        (edge.mVertex[0] == second && edge.mVertex[1] == first)) found = true;
                }
                if (!found) settings->mEdgeConstraints.emplace_back(first, second, 0.00001f);
            }
        }
        settings->CalculateVolumeConstraintVolumes();
    } else {
        for (int row = 0; row < 7; ++row) for (int column = 0; column < 7; ++column) {
            const auto a = row*7+column;
            settings->mVertices.emplace_back(JPH::Float3((column-3)*0.25f, 0, (row-3)*0.25f),
                JPH::Float3(0, 0, 0), scenario == "cloth" && (a == 0 || a == 6) ? 0.0f : 20.0f);
            if (column+1 < 7) settings->mEdgeConstraints.emplace_back(a, a+1, 0.00001f);
            if (row+1 < 7) settings->mEdgeConstraints.emplace_back(a, a+7, 0.00001f);
            if (column+1 < 7 && row+1 < 7) {
                const auto b = a+1, c = a+7, d = c+1;
                settings->mFaces.emplace_back(a, c, b); settings->mFaces.emplace_back(b, c, d);
                settings->mEdgeConstraints.emplace_back(a, d, 0.00001f); settings->mEdgeConstraints.emplace_back(b, c, 0.00001f);
                settings->mDihedralBendConstraints.emplace_back(b, c, a, d, 0.001f);
                if (row+2 < 7) settings->mDihedralBendConstraints.emplace_back(c, d, b, c+7, 0.001f);
                if (column+2 < 7) settings->mDihedralBendConstraints.emplace_back(b, d, c, b+1, 0.001f);
            }
        }
        settings->CalculateBendConstraintConstants();
    }
    settings->CalculateEdgeLengths(); settings->Optimize();
    return settings;
}

// -----------------------------------------------------------------------------

int runSurface(std::string_view scenario) {
    Registration registration;
    auto definition = makeSurface(scenario);
    JPH::BroadPhaseLayerInterfaceTable broadPhase(1, 1);
    broadPhase.MapObjectToBroadPhaseLayer(0, JPH::BroadPhaseLayer(0));
    JPH::ObjectLayerPairFilterTable pairFilter(1); pairFilter.EnableCollision(0, 0);
    JPH::ObjectVsBroadPhaseLayerFilterTable phaseFilter(broadPhase, 1, pairFilter, 1);
    JPH::PhysicsSystem world; world.Init(16, 0, 32, 32, broadPhase, phaseFilter, pairFilter);
    auto& bodies = world.GetBodyInterface();
    JPH::RefConst<JPH::PlaneShape> plane = new JPH::PlaneShape(JPH::Plane(JPH::Vec3::sAxisY(), 0));
    JPH::BodyCreationSettings floorSettings(plane, JPH::RVec3::sZero(), JPH::Quat::sIdentity(), JPH::EMotionType::Static, 0);
    floorSettings.mFriction = 0.6f;
    const auto floor = bodies.CreateAndAddBody(floorSettings, JPH::EActivation::DontActivate);
    JPH::BodyID obstacle;
    if (scenario == "drape") {
        JPH::RefConst<JPH::SphereShape> sphere = new JPH::SphereShape(0.55f);
        JPH::BodyCreationSettings obstacleSettings(sphere, JPH::RVec3(0, 0.6f, 0), JPH::Quat::sIdentity(), JPH::EMotionType::Static, 0);
        obstacleSettings.mFriction = 0.6f;
        obstacle = bodies.CreateAndAddBody(obstacleSettings, JPH::EActivation::DontActivate);
    }
    JPH::SoftBodyCreationSettings settings(definition, JPH::RVec3(0, scenario == "cube" ? 3.0f : 2.0f, 0), JPH::Quat::sIdentity(), 0);
    settings.mNumIterations = 8; settings.mUpdatePosition = false; settings.mAllowSleeping = false;
    settings.mVertexRadius = 0.03f; settings.mFriction = 0.5f;
    auto* body = bodies.CreateSoftBody(settings); if (body == nullptr) return 3;
    bodies.AddBody(body->GetID(), JPH::EActivation::Activate);
    JPH::TempAllocatorImpl allocator(4 * 1024 * 1024);
    JPH::JobSystemSingleThreaded jobs(JPH::cMaxPhysicsJobs);
    for (int i = 0; i < (scenario == "cube" ? 180 : 120); ++i) {
        if (world.Update(1.0f/60.0f, 1, &allocator, &jobs) != JPH::EPhysicsUpdateError::None) return 4;
    }
    const auto* motion = static_cast<const JPH::SoftBodyMotionProperties*>(body->GetMotionProperties());
    float minimum = 100.0f, maximumRatio = 0.0f, penetration = 0.0f;
    for (const auto& vertex : motion->GetVertices()) {
        const auto position = body->GetCenterOfMassPosition()+vertex.mPosition;
        minimum = std::min(minimum, static_cast<float>(position.GetY()));
        if (scenario == "drape") penetration = std::max(penetration, 0.58f-(JPH::Vec3(position)-JPH::Vec3(0, 0.6f, 0)).Length());
    }
    for (const auto& face : definition->mFaces) for (int i = 0; i < 3; ++i) {
        const auto a = face.mVertex[i], b = face.mVertex[(i+1)%3];
        const auto rest = (JPH::Vec3::sLoadFloat3Unsafe(definition->mVertices[a].mPosition)-JPH::Vec3::sLoadFloat3Unsafe(definition->mVertices[b].mPosition)).Length();
        maximumRatio = std::max(maximumRatio, (motion->GetVertices()[a].mPosition-motion->GetVertices()[b].mPosition).Length()/rest);
    }
    std::cout.precision(9);
    std::cout << "volume=" << motion->GetVolume() << " minimum=" << minimum << " strain=" << maximumRatio << " penetration=" << penetration << '\n';
    bodies.RemoveBody(body->GetID()); bodies.DestroyBody(body->GetID());
    if (!obstacle.IsInvalid()) { bodies.RemoveBody(obstacle); bodies.DestroyBody(obstacle); }
    bodies.RemoveBody(floor); bodies.DestroyBody(floor);
    return 0;
}

// -----------------------------------------------------------------------------

int run(std::string_view scenario) {
    Registration registration;
    auto definition = makeDefinition(scenario);
    if (definition == nullptr) return 2;
    JPH::BroadPhaseLayerInterfaceTable broadPhase(1, 1);
    broadPhase.MapObjectToBroadPhaseLayer(0, JPH::BroadPhaseLayer(0));
    JPH::ObjectLayerPairFilterTable pairFilter(1);
    pairFilter.EnableCollision(0, 0);
    JPH::ObjectVsBroadPhaseLayerFilterTable phaseFilter(broadPhase, 1, pairFilter, 1);
    JPH::PhysicsSystem world;
    world.Init(16, 0, 16, 16, broadPhase, phaseFilter, pairFilter);
    world.SetGravity(JPH::Vec3::sZero());
    const bool sweep = scenario == "front-sweep" || scenario == "back-sweep";
    const bool contact = sweep || scenario == "convex-contact" || scenario == "triangle-contact" || scenario == "mesh-contact";
    auto& bodies = world.GetBodyInterface();
    JPH::BodyID rigid;
    if (contact) {
        const JPH::Vec3 a(-2, 0, -2), b(0, 0, 2), c(2, 0, -2);
        JPH::RefConst<JPH::Shape> shape;
        if (scenario == "convex-contact") {
            JPH::Array<JPH::Vec3> points;
            for (int x = -1; x <= 1; x += 2) for (int y = -1; y <= 1; y += 2) for (int z = -1; z <= 1; z += 2)
                points.emplace_back(x*0.5f, y*0.5f, z*0.5f);
            shape = JPH::ConvexHullShapeSettings(points).Create().Get();
        } else if (scenario == "mesh-contact") {
            JPH::TriangleList triangles { JPH::Triangle(a, b, c) };
            shape = JPH::MeshShapeSettings(triangles).Create().Get();
        } else {
            shape = new JPH::TriangleShape(a, b, c);
        }
        JPH::BodyCreationSettings rigidSettings(shape, JPH::RVec3::sZero(), JPH::Quat::sIdentity(), JPH::EMotionType::Static, 0);
        rigid = bodies.CreateAndAddBody(rigidSettings, JPH::EActivation::DontActivate);
    }
    JPH::SoftBodyCreationSettings settings(definition, JPH::RVec3::sZero(), JPH::Quat::sIdentity(), 0);
    settings.mNumIterations = sweep ? 1 : 8;
    settings.mLinearDamping = 0;
    settings.mUpdatePosition = false;
    settings.mAllowSleeping = false;
    settings.mPressure = scenario == "pressure" ? 0.1f : 0;
    settings.mVertexRadius = contact ? 0.03f : 0;
    auto* body = bodies.CreateSoftBody(settings);
    if (body == nullptr) return 3;
    bodies.AddBody(body->GetID(), JPH::EActivation::Activate);
    JPH::TempAllocatorImpl allocator(4 * 1024 * 1024);
    JPH::JobSystemSingleThreaded jobs(JPH::cMaxPhysicsJobs);
    for (int frame = 0; frame < (contact ? 1 : 12); ++frame) {
        if (world.Update(1.0f / 60.0f, 1, &allocator, &jobs) != JPH::EPhysicsUpdateError::None) return 4;
    }
    const auto* motion = static_cast<const JPH::SoftBodyMotionProperties*>(body->GetMotionProperties());
    std::cout.precision(9);
    for (const auto& vertex : motion->GetVertices()) {
        const auto position = body->GetCenterOfMassPosition() + vertex.mPosition;
        std::cout << position.GetX() << ' ' << position.GetY() << ' ' << position.GetZ() << ' '
            << vertex.mVelocity.GetX() << ' ' << vertex.mVelocity.GetY() << ' ' << vertex.mVelocity.GetZ() << '\n';
    }
    bodies.RemoveBody(body->GetID());
    bodies.DestroyBody(body->GetID());
    if (!rigid.IsInvalid()) { bodies.RemoveBody(rigid); bodies.DestroyBody(rigid); }
    return 0;
}

// -----------------------------------------------------------------------------

} // namespace Physics3D

int main(int count, char** values) {
    if (count == 2 && std::string_view(values[1]) == "--configuration") {
        std::cout << JPH::GetConfigurationString() << '\n';
        return 0;
    }
    if (count != 2) return 2;
    const std::string_view scenario(values[1]);
    if (scenario == "cube" || scenario == "cloth" || scenario == "drape") return Physics3D::runSurface(scenario);
    return Physics3D::run(values[1]);
}
