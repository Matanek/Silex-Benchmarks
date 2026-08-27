#include <algorithm>
#include <array>
#include <charconv>
#include <chrono>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <numbers>
#include <random>
#include <span>
#include <vector>

#include <SDL3/SDL.h>
#include <entt/entt.hpp>

namespace Boids {

// -----------------------------------------------------------------------------

constexpr float k_neighborhoodRadius = 72.0F;
constexpr float k_separationRadius = 28.0F;
constexpr float k_minimumSpeed = 55.0F;
constexpr float k_maximumSpeed = 105.0F;
constexpr float k_maximumSteering = 140.0F;
constexpr float k_halfWidth = 490.0F;
constexpr float k_halfHeight = 330.0F;
constexpr int k_windowWidth = 960;
constexpr int k_windowHeight = 640;
constexpr float k_neighborhoodRadiusSquared =
    k_neighborhoodRadius * k_neighborhoodRadius;
constexpr float k_separationRadiusSquared =
    k_separationRadius * k_separationRadius;

struct Vector2 {
    float x { 0.0F };
    float y { 0.0F };
};

struct Boid {
    Vector2 position;
    Vector2 velocity;
};

struct Transform {
    Vector2 position;
    float rotation { 0.0F };
};

struct Renderable {
    int order { 0 };
    std::array<float, 4> color;
};

struct Camera {};

struct Sample {
    float positionX { 0.0F };
    float positionY { 0.0F };
    float velocityX { 0.0F };
    float velocityY { 0.0F };
};

struct Steering {
    float x { 0.0F };
    float y { 0.0F };
};

struct DrawingVertex {
    std::array<float, 3> position;
    std::array<float, 3> shape;
    std::array<float, 2> local;
    std::array<Uint8, 4> color;
};

struct DrawingInstance {
    std::array<float, 2> modelX;
    std::array<float, 2> modelY;
    std::array<float, 2> modelTranslation;
    float modelDepth { 0.0F };
    float padding { 0.0F };
    std::array<float, 4> materialColor;
};

struct ViewUniforms {
    std::array<float, 16> viewProjection;
};

static_assert(sizeof(DrawingVertex) == 36);
static_assert(sizeof(DrawingInstance) == 48);
static_assert(sizeof(ViewUniforms) == 64);

// -----------------------------------------------------------------------------

Vector2 operator+(Vector2 lhs, Vector2 rhs) {
    return { lhs.x + rhs.x, lhs.y + rhs.y };
}

Vector2 operator*(Vector2 value, float scalar) {
    return { value.x * scalar, value.y * scalar };
}

float lengthSquared(Vector2 value) {
    return value.x * value.x + value.y * value.y;
}

float length(Vector2 value) {
    return std::sqrt(lengthSquared(value));
}

Vector2 limit(Vector2 value, float maximum) {
    const float currentLength = length(value);
    return currentLength > maximum ? value * (maximum / currentLength) : value;
}

Vector2 keepSpeed(Vector2 value) {
    const float speed = length(value);
    if (speed > k_maximumSpeed) return value * (k_maximumSpeed / speed);
    if (speed < k_minimumSpeed && speed > 0.0F) {
        return value * (k_minimumSpeed / speed);
    }
    return value;
}

Vector2 wrap(Vector2 position) {
    if (position.x < -k_halfWidth) {
        position.x = k_halfWidth;
    } else if (position.x > k_halfWidth) {
        position.x = -k_halfWidth;
    }
    if (position.y < -k_halfHeight) {
        position.y = k_halfHeight;
    } else if (position.y > k_halfHeight) {
        position.y = -k_halfHeight;
    }
    return position;
}

Steering steering(Vector2 position, Vector2 velocity, std::span<const Sample> snapshot) {
    float separationX = 0.0F;
    float separationY = 0.0F;
    float centerX = 0.0F;
    float centerY = 0.0F;
    float headingX = 0.0F;
    float headingY = 0.0F;
    int neighbors = 0;

    for (const Sample& other : snapshot) {
        const float offsetX = position.x - other.positionX;
        const float offsetY = position.y - other.positionY;
        const float distanceSquared = offsetX * offsetX + offsetY * offsetY;
        if (distanceSquared > 0.0F
            && distanceSquared < k_neighborhoodRadiusSquared) {
            centerX += other.positionX;
            centerY += other.positionY;
            headingX += other.velocityX;
            headingY += other.velocityY;
            ++neighbors;
            if (distanceSquared < k_separationRadiusSquared) {
                const float divisor = std::max(distanceSquared, 1.0F);
                separationX += offsetX / divisor;
                separationY += offsetY / divisor;
            }
        }
    }

    if (neighbors == 0) return {};
    const float count = static_cast<float>(neighbors);
    return {
        (centerX / count - position.x) * 0.35F
            + (headingX / count - velocity.x) * 0.8F
            + separationX * 1400.0F,
        (centerY / count - position.y) * 0.35F
            + (headingY / count - velocity.y) * 0.8F
            + separationY * 1400.0F
    };
}

int parseCount(const char* text) {
    int value = 100;
    const auto result = std::from_chars(
        text,
        text + std::char_traits<char>::length(text),
        value
    );
    return result.ec == std::errc {} && value > 0 ? value : 100;
}

// -----------------------------------------------------------------------------

class ArchitecturalBenchmark {

    // -------------------------------------------------------------------------
    // LIFECYCLE

    public: explicit ArchitecturalBenchmark(int count) : count(count) {}
    public: ArchitecturalBenchmark(const ArchitecturalBenchmark&) = delete;
    public: ArchitecturalBenchmark& operator=(const ArchitecturalBenchmark&) = delete;
    public: ~ArchitecturalBenchmark();

    // -------------------------------------------------------------------------
    // API

    public: bool initialize();
    public: int run();

    // -------------------------------------------------------------------------
    // INTERNALS

    private: bool initializeWindow();
    private: bool initializePipeline();
    private: bool initializeBuffers();
    private: void initializeFlock();
    private: SDL_GPUShader* loadShader(
        const char* path,
        SDL_GPUShaderStage stage,
        Uint32 uniformBuffers
    );
    private: bool uploadStaticGeometry();
    private: void captureFlock();
    private: void moveFlock(float delta);
    private: void collectScene();
    private: bool uploadInstances();
    private: bool render();
    private: bool fail(const char* action) const;

    private: int count { 0 };
    private: entt::registry registry;
    private: std::vector<Sample> snapshot;
    private: std::vector<DrawingInstance> instances;
    private: SDL_Window* window { nullptr };
    private: SDL_GPUDevice* device { nullptr };
    private: SDL_GPUGraphicsPipeline* pipeline { nullptr };
    private: SDL_GPUBuffer* vertexBuffer { nullptr };
    private: SDL_GPUBuffer* instanceBuffer { nullptr };
    private: SDL_GPUTransferBuffer* instanceUpload { nullptr };
    private: ViewUniforms uniforms {};
};

// -----------------------------------------------------------------------------

ArchitecturalBenchmark::~ArchitecturalBenchmark() {
    if (device != nullptr) SDL_WaitForGPUIdle(device);
    if (pipeline != nullptr) SDL_ReleaseGPUGraphicsPipeline(device, pipeline);
    if (vertexBuffer != nullptr) SDL_ReleaseGPUBuffer(device, vertexBuffer);
    if (instanceBuffer != nullptr) SDL_ReleaseGPUBuffer(device, instanceBuffer);
    if (instanceUpload != nullptr) {
        SDL_ReleaseGPUTransferBuffer(device, instanceUpload);
    }
    if (device != nullptr && window != nullptr) {
        SDL_ReleaseWindowFromGPUDevice(device, window);
    }
    if (device != nullptr) SDL_DestroyGPUDevice(device);
    if (window != nullptr) SDL_DestroyWindow(window);
    SDL_Quit();
}

bool ArchitecturalBenchmark::initialize() {
    if (!initializeWindow()) return false;
    if (!initializePipeline()) return false;
    if (!initializeBuffers()) return false;
    initializeFlock();
    return true;
}

int ArchitecturalBenchmark::run() {
    using Clock = std::chrono::steady_clock;
    auto previous = Clock::now();
    const auto start = previous;
    int frames = 0;

    while (std::chrono::duration<float>(Clock::now() - start).count() < 5.0F) {
        SDL_Event event;
        while (SDL_PollEvent(&event)) {}

        const auto now = Clock::now();
        const float delta = std::chrono::duration<float>(now - previous).count();
        previous = now;

        captureFlock();
        moveFlock(delta);
        collectScene();
        if (!uploadInstances() || !render()) return EXIT_FAILURE;
        ++frames;
    }

    const float seconds = std::chrono::duration<float>(Clock::now() - start).count();
    int windowWidth = 0;
    int windowHeight = 0;
    int pixelWidth = 0;
    int pixelHeight = 0;
    if (!SDL_GetWindowSize(window, &windowWidth, &windowHeight)
        || !SDL_GetWindowSizeInPixels(window, &pixelWidth, &pixelHeight)) {
        fail("query benchmark dimensions");
        return EXIT_FAILURE;
    }

    std::printf(
        "CPP_ARCHITECTURAL_BOIDS count=%d ecs=entt renderer=sdl_gpu "
        "present=immediate fps=%.5f window=%dx%d pixels=%dx%d "
        "scale=%.5f density=%.5f\n",
        count,
        static_cast<double>(frames) / seconds,
        windowWidth,
        windowHeight,
        pixelWidth,
        pixelHeight,
        static_cast<double>(SDL_GetWindowDisplayScale(window)),
        static_cast<double>(SDL_GetWindowPixelDensity(window))
    );
    return EXIT_SUCCESS;
}

// -----------------------------------------------------------------------------

bool ArchitecturalBenchmark::initializeWindow() {
    if (!SDL_Init(SDL_INIT_VIDEO)) return fail("initialize SDL");

#if defined(BOIDS_SHADER_FORMAT_MSL)
    constexpr SDL_GPUShaderFormat k_shaderFormat = SDL_GPU_SHADERFORMAT_MSL;
#elif defined(BOIDS_SHADER_FORMAT_DXIL)
    constexpr SDL_GPUShaderFormat k_shaderFormat = SDL_GPU_SHADERFORMAT_DXIL;
#else
    constexpr SDL_GPUShaderFormat k_shaderFormat = SDL_GPU_SHADERFORMAT_SPIRV;
#endif

    device = SDL_CreateGPUDevice(k_shaderFormat, false, nullptr);
    if (device == nullptr) return fail("create GPU device");

    window = SDL_CreateWindow(
        "C++ Architectural GPU Boids",
        k_windowWidth,
        k_windowHeight,
        SDL_WINDOW_HIGH_PIXEL_DENSITY
    );
    if (window == nullptr) return fail("create window");
    if (!SDL_ClaimWindowForGPUDevice(device, window)) {
        return fail("claim window for GPU device");
    }
    if (!SDL_WindowSupportsGPUPresentMode(
            device,
            window,
            SDL_GPU_PRESENTMODE_IMMEDIATE
        )) {
        return fail("select immediate GPU presentation");
    }
    if (!SDL_SetGPUSwapchainParameters(
            device,
            window,
            SDL_GPU_SWAPCHAINCOMPOSITION_SDR,
            SDL_GPU_PRESENTMODE_IMMEDIATE
        )) {
        return fail("configure GPU swapchain");
    }
    return true;
}

bool ArchitecturalBenchmark::initializePipeline() {
    SDL_GPUShader* vertexShader = loadShader(
        BOIDS_VERTEX_SHADER_PATH,
        SDL_GPU_SHADERSTAGE_VERTEX,
        1
    );
    if (vertexShader == nullptr) return false;
    SDL_GPUShader* fragmentShader = loadShader(
        BOIDS_FRAGMENT_SHADER_PATH,
        SDL_GPU_SHADERSTAGE_FRAGMENT,
        0
    );
    if (fragmentShader == nullptr) {
        SDL_ReleaseGPUShader(device, vertexShader);
        return false;
    }

    const std::array<SDL_GPUVertexBufferDescription, 2> buffers {{
        { 0, sizeof(DrawingVertex), SDL_GPU_VERTEXINPUTRATE_VERTEX, 0 },
        { 1, sizeof(DrawingInstance), SDL_GPU_VERTEXINPUTRATE_INSTANCE, 0 }
    }};
    const std::array<SDL_GPUVertexAttribute, 9> attributes {{
        { 0, 0, SDL_GPU_VERTEXELEMENTFORMAT_FLOAT3, 0 },
        { 1, 0, SDL_GPU_VERTEXELEMENTFORMAT_FLOAT3, 12 },
        { 2, 0, SDL_GPU_VERTEXELEMENTFORMAT_FLOAT2, 24 },
        { 3, 0, SDL_GPU_VERTEXELEMENTFORMAT_UBYTE4_NORM, 32 },
        { 4, 1, SDL_GPU_VERTEXELEMENTFORMAT_FLOAT2, 0 },
        { 5, 1, SDL_GPU_VERTEXELEMENTFORMAT_FLOAT2, 8 },
        { 6, 1, SDL_GPU_VERTEXELEMENTFORMAT_FLOAT2, 16 },
        { 7, 1, SDL_GPU_VERTEXELEMENTFORMAT_FLOAT, 24 },
        { 8, 1, SDL_GPU_VERTEXELEMENTFORMAT_FLOAT4, 32 }
    }};

    SDL_GPUColorTargetDescription colorTarget {};
    colorTarget.format = SDL_GetGPUSwapchainTextureFormat(device, window);
    colorTarget.blend_state.src_color_blendfactor =
        SDL_GPU_BLENDFACTOR_SRC_ALPHA;
    colorTarget.blend_state.dst_color_blendfactor =
        SDL_GPU_BLENDFACTOR_ONE_MINUS_SRC_ALPHA;
    colorTarget.blend_state.color_blend_op = SDL_GPU_BLENDOP_ADD;
    colorTarget.blend_state.src_alpha_blendfactor = SDL_GPU_BLENDFACTOR_ONE;
    colorTarget.blend_state.dst_alpha_blendfactor =
        SDL_GPU_BLENDFACTOR_ONE_MINUS_SRC_ALPHA;
    colorTarget.blend_state.alpha_blend_op = SDL_GPU_BLENDOP_ADD;
    colorTarget.blend_state.color_write_mask = 0xF;
    colorTarget.blend_state.enable_blend = true;
    colorTarget.blend_state.enable_color_write_mask = true;

    SDL_GPUGraphicsPipelineCreateInfo info {};
    info.vertex_shader = vertexShader;
    info.fragment_shader = fragmentShader;
    info.vertex_input_state.vertex_buffer_descriptions = buffers.data();
    info.vertex_input_state.num_vertex_buffers = buffers.size();
    info.vertex_input_state.vertex_attributes = attributes.data();
    info.vertex_input_state.num_vertex_attributes = attributes.size();
    info.primitive_type = SDL_GPU_PRIMITIVETYPE_TRIANGLELIST;
    info.rasterizer_state.fill_mode = SDL_GPU_FILLMODE_FILL;
    info.rasterizer_state.cull_mode = SDL_GPU_CULLMODE_NONE;
    info.rasterizer_state.front_face = SDL_GPU_FRONTFACE_COUNTER_CLOCKWISE;
    info.rasterizer_state.enable_depth_clip = true;
    info.multisample_state.sample_count = SDL_GPU_SAMPLECOUNT_1;
    info.target_info.color_target_descriptions = &colorTarget;
    info.target_info.num_color_targets = 1;

    pipeline = SDL_CreateGPUGraphicsPipeline(device, &info);
    SDL_ReleaseGPUShader(device, vertexShader);
    SDL_ReleaseGPUShader(device, fragmentShader);
    if (pipeline == nullptr) return fail("create graphics pipeline");
    return true;
}

bool ArchitecturalBenchmark::initializeBuffers() {
    SDL_GPUBufferCreateInfo vertexInfo {};
    vertexInfo.usage = SDL_GPU_BUFFERUSAGE_VERTEX;
    vertexInfo.size = sizeof(DrawingVertex) * 3;
    vertexBuffer = SDL_CreateGPUBuffer(device, &vertexInfo);
    if (vertexBuffer == nullptr) return fail("create drawing vertex buffer");

    SDL_GPUBufferCreateInfo instanceInfo {};
    instanceInfo.usage = SDL_GPU_BUFFERUSAGE_VERTEX;
    instanceInfo.size = sizeof(DrawingInstance) * count;
    instanceBuffer = SDL_CreateGPUBuffer(device, &instanceInfo);
    if (instanceBuffer == nullptr) return fail("create drawing instance buffer");

    SDL_GPUTransferBufferCreateInfo uploadInfo {};
    uploadInfo.usage = SDL_GPU_TRANSFERBUFFERUSAGE_UPLOAD;
    uploadInfo.size = sizeof(DrawingInstance) * count;
    instanceUpload = SDL_CreateGPUTransferBuffer(device, &uploadInfo);
    if (instanceUpload == nullptr) return fail("create instance upload buffer");

    uniforms.viewProjection = {
        2.0F / static_cast<float>(k_windowWidth), 0.0F, 0.0F, 0.0F,
        0.0F, 2.0F / static_cast<float>(k_windowHeight), 0.0F, 0.0F,
        0.0F, 0.0F, -1.0F, 0.0F,
        0.0F, 0.0F, 0.0F, 1.0F
    };
    return uploadStaticGeometry();
}

void ArchitecturalBenchmark::initializeFlock() {
    registry.emplace<Camera>(registry.create());
    snapshot.reserve(count);
    instances.reserve(count);

    std::mt19937 randomizer { 0x511E801D };
    std::uniform_real_distribution<float> xPosition { -k_halfWidth, k_halfWidth };
    std::uniform_real_distribution<float> yPosition { -k_halfHeight, k_halfHeight };
    std::uniform_real_distribution<float> angleDistribution {
        0.0F,
        2.0F * std::numbers::pi_v<float>
    };
    std::uniform_real_distribution<float> speedDistribution {
        k_minimumSpeed,
        k_maximumSpeed
    };
    constexpr std::array<std::array<float, 4>, 3> k_colors {{
        { 0.49F, 0.83F, 0.99F, 1.0F },
        { 0.13F, 0.83F, 0.93F, 1.0F },
        { 0.51F, 0.55F, 0.97F, 1.0F }
    }};

    for (int index = 0; index < count; ++index) {
        const float angle = angleDistribution(randomizer);
        const float speed = speedDistribution(randomizer);
        const Vector2 position { xPosition(randomizer), yPosition(randomizer) };
        const Vector2 velocity {
            std::cos(angle) * speed,
            std::sin(angle) * speed
        };
        const entt::entity entity = registry.create();
        registry.emplace<Boid>(entity, position, velocity);
        registry.emplace<Transform>(entity, position, angle);
        registry.emplace<Renderable>(
            entity,
            index,
            k_colors[static_cast<std::size_t>(index % 3)]
        );
    }

    registry.sort<Renderable>(
        [](const Renderable& lhs, const Renderable& rhs) {
            return lhs.order < rhs.order;
        }
    );
}

SDL_GPUShader* ArchitecturalBenchmark::loadShader(
    const char* path,
    SDL_GPUShaderStage stage,
    Uint32 uniformBuffers
) {
    std::size_t size = 0;
    void* bytes = SDL_LoadFile(path, &size);
    if (bytes == nullptr) {
        fail("load compiled shader");
        return nullptr;
    }

#if defined(BOIDS_SHADER_FORMAT_MSL)
    constexpr SDL_GPUShaderFormat k_shaderFormat = SDL_GPU_SHADERFORMAT_MSL;
#elif defined(BOIDS_SHADER_FORMAT_DXIL)
    constexpr SDL_GPUShaderFormat k_shaderFormat = SDL_GPU_SHADERFORMAT_DXIL;
#else
    constexpr SDL_GPUShaderFormat k_shaderFormat = SDL_GPU_SHADERFORMAT_SPIRV;
#endif

    SDL_GPUShaderCreateInfo info {};
    info.code_size = size;
    info.code = static_cast<const Uint8*>(bytes);
    info.entrypoint = stage == SDL_GPU_SHADERSTAGE_VERTEX
        ? "vertex_main"
        : "fragment_main";
    info.format = k_shaderFormat;
    info.stage = stage;
    info.num_uniform_buffers = uniformBuffers;
    SDL_GPUShader* shader = SDL_CreateGPUShader(device, &info);
    SDL_free(bytes);
    if (shader == nullptr) fail("create GPU shader");
    return shader;
}

bool ArchitecturalBenchmark::uploadStaticGeometry() {
    constexpr std::array<DrawingVertex, 3> k_vertices {{
        { { 8.0F, 0.0F, -1.0F }, {}, {}, { 255, 255, 255, 255 } },
        { { -7.0F, 6.0F, -1.0F }, {}, {}, { 255, 255, 255, 255 } },
        { { -7.0F, -6.0F, -1.0F }, {}, {}, { 255, 255, 255, 255 } }
    }};
    SDL_GPUTransferBufferCreateInfo info {};
    info.usage = SDL_GPU_TRANSFERBUFFERUSAGE_UPLOAD;
    info.size = sizeof(k_vertices);
    SDL_GPUTransferBuffer* upload = SDL_CreateGPUTransferBuffer(device, &info);
    if (upload == nullptr) return fail("create vertex upload buffer");
    void* destination = SDL_MapGPUTransferBuffer(device, upload, false);
    if (destination == nullptr) {
        SDL_ReleaseGPUTransferBuffer(device, upload);
        return fail("map vertex upload buffer");
    }
    std::memcpy(destination, k_vertices.data(), sizeof(k_vertices));
    SDL_UnmapGPUTransferBuffer(device, upload);

    SDL_GPUCommandBuffer* commands = SDL_AcquireGPUCommandBuffer(device);
    if (commands == nullptr) {
        SDL_ReleaseGPUTransferBuffer(device, upload);
        return fail("acquire vertex upload commands");
    }
    SDL_GPUCopyPass* copy = SDL_BeginGPUCopyPass(commands);
    SDL_GPUTransferBufferLocation source { upload, 0 };
    SDL_GPUBufferRegion target { vertexBuffer, 0, sizeof(k_vertices) };
    SDL_UploadToGPUBuffer(copy, &source, &target, false);
    SDL_EndGPUCopyPass(copy);
    if (!SDL_SubmitGPUCommandBuffer(commands)) {
        SDL_ReleaseGPUTransferBuffer(device, upload);
        return fail("submit vertex upload");
    }
    SDL_ReleaseGPUTransferBuffer(device, upload);
    return true;
}

// -----------------------------------------------------------------------------

void ArchitecturalBenchmark::captureFlock() {
    snapshot.clear();
    auto view = registry.view<const Boid, const Transform, const Renderable>();
    view.use<Renderable>();
    for (auto [entity, boid, transform, rendered] : view.each()) {
        static_cast<void>(entity);
        static_cast<void>(transform);
        static_cast<void>(rendered);
        snapshot.push_back({
            boid.position.x,
            boid.position.y,
            boid.velocity.x,
            boid.velocity.y
        });
    }
}

void ArchitecturalBenchmark::moveFlock(float delta) {
    auto view = registry.view<Boid, Transform, const Renderable>();
    view.use<Renderable>();
    for (auto [entity, boid, transform, rendered] : view.each()) {
        static_cast<void>(entity);
        static_cast<void>(rendered);
        const Steering raw = steering(boid.position, boid.velocity, snapshot);
        const Vector2 acceleration = limit({ raw.x, raw.y }, k_maximumSteering);
        boid.velocity = keepSpeed(boid.velocity + acceleration * delta);
        boid.position = wrap(boid.position + boid.velocity * delta);
        transform.position = boid.position;
        transform.rotation = std::atan2(boid.velocity.y, boid.velocity.x);
    }
}

void ArchitecturalBenchmark::collectScene() {
    instances.clear();
    auto view = registry.view<const Transform, const Renderable>();
    view.use<Renderable>();
    for (auto [entity, transform, rendered] : view.each()) {
        static_cast<void>(entity);
        const float cosine = std::cos(transform.rotation);
        const float sine = std::sin(transform.rotation);
        instances.push_back({
            { cosine, sine },
            { -sine, cosine },
            { transform.position.x, transform.position.y },
            0.0F,
            0.0F,
            rendered.color
        });
    }
}

bool ArchitecturalBenchmark::uploadInstances() {
    const Uint32 byteCount = static_cast<Uint32>(
        instances.size() * sizeof(DrawingInstance)
    );
    void* destination = SDL_MapGPUTransferBuffer(device, instanceUpload, true);
    if (destination == nullptr) return fail("map instance upload buffer");
    std::memcpy(destination, instances.data(), byteCount);
    SDL_UnmapGPUTransferBuffer(device, instanceUpload);

    SDL_GPUCommandBuffer* commands = SDL_AcquireGPUCommandBuffer(device);
    if (commands == nullptr) return fail("acquire instance upload commands");
    SDL_GPUCopyPass* copy = SDL_BeginGPUCopyPass(commands);
    SDL_GPUTransferBufferLocation source { instanceUpload, 0 };
    SDL_GPUBufferRegion target { instanceBuffer, 0, byteCount };
    SDL_UploadToGPUBuffer(copy, &source, &target, true);
    SDL_EndGPUCopyPass(copy);
    if (!SDL_SubmitGPUCommandBuffer(commands)) {
        return fail("submit instance upload");
    }
    return true;
}

bool ArchitecturalBenchmark::render() {
    SDL_GPUCommandBuffer* commands = SDL_AcquireGPUCommandBuffer(device);
    if (commands == nullptr) return fail("acquire render commands");

    SDL_GPUTexture* swapchain = nullptr;
    if (!SDL_WaitAndAcquireGPUSwapchainTexture(
            commands,
            window,
            &swapchain,
            nullptr,
            nullptr
        )) {
        SDL_CancelGPUCommandBuffer(commands);
        return fail("acquire GPU swapchain texture");
    }
    if (swapchain == nullptr) {
        return SDL_SubmitGPUCommandBuffer(commands);
    }

    SDL_PushGPUVertexUniformData(commands, 0, &uniforms, sizeof(uniforms));
    SDL_GPUColorTargetInfo target {};
    target.texture = swapchain;
    target.clear_color = { 0.0F, 0.0F, 0.0F, 1.0F };
    target.load_op = SDL_GPU_LOADOP_CLEAR;
    target.store_op = SDL_GPU_STOREOP_STORE;
    SDL_GPURenderPass* pass = SDL_BeginGPURenderPass(commands, &target, 1, nullptr);
    SDL_BindGPUGraphicsPipeline(pass, pipeline);
    const std::array<SDL_GPUBufferBinding, 2> bindings {{
        { vertexBuffer, 0 },
        { instanceBuffer, 0 }
    }};
    SDL_BindGPUVertexBuffers(pass, 0, bindings.data(), bindings.size());
    SDL_DrawGPUPrimitives(
        pass,
        3,
        static_cast<Uint32>(instances.size()),
        0,
        0
    );
    SDL_EndGPURenderPass(pass);
    if (!SDL_SubmitGPUCommandBuffer(commands)) return fail("submit render");
    return true;
}

bool ArchitecturalBenchmark::fail(const char* action) const {
    std::fprintf(stderr, "Could not %s: %s\n", action, SDL_GetError());
    return false;
}

// -----------------------------------------------------------------------------

} // namespace Boids

int main(int argc, char** argv) {
    const int count = argc > 1 ? Boids::parseCount(argv[1]) : 100;
    Boids::ArchitecturalBenchmark benchmark(count);
    if (!benchmark.initialize()) return EXIT_FAILURE;
    return benchmark.run();
}
