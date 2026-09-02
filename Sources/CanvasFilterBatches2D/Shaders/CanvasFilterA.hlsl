struct VertexInput {
    float2 position : POSITION0;
    float2 uv : TEXCOORD0;
};

struct VertexOutput {
    float4 position : SV_Position;
    float2 uv : TEXCOORD0;
};

cbuffer Scene2DCanvasFilter : register(b0, space1) {
    float4x4 clipFromUnit;
    float2 logicalOrigin;
    float2 logicalSize;
    float2 pixelSize;
    float2 inversePixelSize;
};

cbuffer FilterParameters : register(b1, space1) {
    float4 multiplier;
};

Texture2D<float4> sourceTexture : register(t0, space2);
SamplerState sourceSampler : register(s0, space2);

VertexOutput vertex_main(VertexInput input) {
    VertexOutput output;
    output.position = mul(clipFromUnit, float4(input.position, 0.0, 1.0));
    output.uv = input.uv;
    return output;
}

float4 fragment_main(VertexOutput input) : SV_Target0 {
    const float2 pixel = min(floor(input.uv * pixelSize), pixelSize - 1.0);
    const float2 center = (pixel + 0.5) * inversePixelSize;
    return sourceTexture.SampleLevel(sourceSampler, center, 0.0) * multiplier;
}
