#pragma once

#include <array>
#include <cstdint>
#include <map>
#include <memory>
#include <optional>
#include <string>
#include <unordered_map>
#include <utility>
#include <vector>

namespace mvq {

enum class LabelClass : std::uint8_t {
  kBackground = 0,
  kAnnulus = 1,
  kAnteriorLeaflet = 2,
  kPosteriorLeaflet = 3,
  kAorticValve = 4,
};

enum class CardiacPhase : std::uint8_t {
  kUnknown = 0,
  kEndDiastole = 1,
  kMidSystole = 2,
  kEndSystole = 3,
};

enum class LandmarkId : std::uint8_t {
  kAnteriorAnnulus = 0,
  kPosteriorAnnulus,
  kAnterolateralCommissure,
  kPosteromedialCommissure,
  kLeftTrigone,
  kRightTrigone,
  kCoaptationMidpoint,
  kCoaptationAL,
  kCoaptationPM,
  kAorticCenter,
  kAorticReference,
  kApicalReference,
};

enum class MeasurementId : std::uint8_t {
  kAnnulusPerimeter3D = 0,
  kAnnulusArea3D,
  kAnnulusArea2D,
  kAPDiameter,
  kALPMDiameter,
  kCommissuralDiameter,
  kInterTrigonalDistance,
  kDShapeArea2D,
  kDShapePerimeter,
  kAnnulusHeight,
  kNonPlanarAngle,
  kMitralAorticAngle,
  kMitralAnnularExcursion,
  kAnnularAreaFraction,
  kAnnularVelocity,
  kAnteriorLeafletArea,
  kPosteriorLeafletArea,
  kAnteriorLeafletLength,
  kPosteriorLeafletLength,
  kAnteriorLeafletAngle,
  kPosteriorLeafletAngle,
  kTentingHeight,
  kTentingArea,
  kTentingVolume,
  kBillowingHeight,
  kBillowingArea,
  kBillowingVolume,
  kCoaptationLength,
  kCoaptationArea,
  kOrificeArea,
};

struct Vec2d {
  double x = 0.0;
  double y = 0.0;
};

struct Vec3d {
  double x = 0.0;
  double y = 0.0;
  double z = 0.0;
};

struct Mat3d {
  std::array<double, 9> m = {1.0, 0.0, 0.0,
                             0.0, 1.0, 0.0,
                             0.0, 0.0, 1.0};
};

struct Plane3d {
  Vec3d origin;
  Vec3d normal;
};

struct Axis3d {
  Vec3d origin;
  Vec3d direction;
};

struct BoundingBox3d {
  Vec3d min;
  Vec3d max;
};

struct ScalarMeasurement {
  MeasurementId id = MeasurementId::kAnnulusPerimeter3D;
  std::string name;
  std::string unit;
  double value = 0.0;
  bool is_valid = false;
};

struct Landmark {
  LandmarkId id = LandmarkId::kAnteriorAnnulus;
  Vec3d position;
  double confidence = 0.0;
  bool is_locked = false;
  bool user_edited = false;
};

struct LandmarkSet {
  std::unordered_map<LandmarkId, Landmark> points;
};

struct LandmarkCandidate {
  LandmarkId id = LandmarkId::kAnteriorAnnulus;
  Vec3d position;
  double confidence = 0.0;
  std::string source;
};

struct LandmarkCandidateSet {
  std::unordered_map<LandmarkId, std::vector<LandmarkCandidate>> points;
};

struct VoxelQualityMap {
  std::vector<float> values;
  std::array<std::int32_t, 3> dims = {0, 0, 0};
};

template <typename T>
struct VolumeGrid {
  std::vector<T> data;
  std::array<std::int32_t, 3> dims = {0, 0, 0};
  Vec3d spacing_mm;
  Vec3d origin_mm;
  Mat3d direction;
};

using IntensityVolume = VolumeGrid<float>;
using ProbabilityVolume = VolumeGrid<float>;
using DistanceFieldVolume = VolumeGrid<float>;
using LabelVolume = VolumeGrid<std::uint8_t>;

struct PointCloud3d {
  std::vector<Vec3d> points;
  std::vector<float> weights;
};

struct ConnectedComponentStats {
  LabelClass label = LabelClass::kBackground;
  std::int32_t component_id = -1;
  std::size_t voxel_count = 0;
  BoundingBox3d bounds;
  Vec3d centroid;
  double mean_quality = 0.0;
};

struct VolumeEvidence {
  IntensityVolume intensity;
  std::optional<LabelVolume> hard_labels;
  std::unordered_map<LabelClass, ProbabilityVolume> probabilities;
  std::unordered_map<LabelClass, DistanceFieldVolume> signed_distance_fields;
  std::unordered_map<LabelClass, DistanceFieldVolume> boundary_shell_fields;
  std::unordered_map<LabelClass, VoxelQualityMap> derived_quality_maps;
};

struct TensorDerivedData {
  VolumeEvidence evidence;
  std::unordered_map<LabelClass, PointCloud3d> point_clouds;
  std::vector<ConnectedComponentStats> components;
  LandmarkCandidateSet candidate_landmarks;
};

struct CurveSample {
  double u = 0.0;
  Vec3d position;
};

struct Polyline3d {
  std::vector<Vec3d> points;
  bool closed = false;
};

struct SplineCurve3d {
  std::vector<Vec3d> control_points;
  std::vector<double> knots;
  std::int32_t degree = 3;
  bool periodic = false;
};

struct Triangle {
  std::array<std::int32_t, 3> indices = {0, 0, 0};
};

struct SurfaceMesh {
  std::vector<Vec3d> vertices;
  std::vector<Vec3d> normals;
  std::vector<Triangle> faces;
  std::vector<double> scalar_field;
};

struct HeatmapField {
  std::string name;
  std::string unit;
  std::vector<double> values;
  double min_value = 0.0;
  double max_value = 0.0;
};

struct AnnulusModel {
  SplineCurve3d spline;
  Plane3d best_fit_plane;
  Plane3d d_shape_plane;
  Axis3d ap_axis;
  Axis3d commissural_axis;
  BoundingBox3d bounds;
  LandmarkSet anchors;
  Polyline3d sampled_curve;
};

struct LeafletBoundary {
  Polyline3d attachment;
  Polyline3d free_edge;
  Polyline3d centerline;
};

struct LeafletModel {
  SurfaceMesh control_mesh;
  SurfaceMesh render_mesh;
  LeafletBoundary boundaries;
  HeatmapField signed_height_map;
  HeatmapField signed_saddle_height_map;
  LabelClass label = LabelClass::kAnteriorLeaflet;
};

struct AorticModel {
  Plane3d annulus_plane;
  SplineCurve3d annulus_curve;
  Axis3d root_axis;
  LandmarkSet anchors;
};

struct CoaptationModel {
  Polyline3d centerline;
  SurfaceMesh contact_patch;
  std::optional<SurfaceMesh> orifice_patch;
};

struct MitralValveModel {
  CardiacPhase phase = CardiacPhase::kUnknown;
  std::int32_t frame_index = -1;
  AnnulusModel annulus;
  LeafletModel anterior_leaflet;
  LeafletModel posterior_leaflet;
  AorticModel aortic;
  CoaptationModel coaptation;
  LandmarkSet landmarks;
  std::map<MeasurementId, ScalarMeasurement> measurements;
  bool approved = false;
};

struct ReconstructionOptions {
  bool hard_label_only_input = true;
  bool use_probability_volumes = true;
  bool use_signed_distance_fields = true;
  bool derive_confidence_from_labels = true;
  bool enable_d_shape_measurements = true;
  bool enable_temporal_tracking = false;
  bool compute_extended_measurements = true;
  std::int32_t annulus_control_points = 28;
  std::int32_t leaflet_subdivision_level = 2;
  double annulus_fit_weight = 1.0;
  double landmark_weight = 3.0;
  double leaflet_attach_weight = 5.0;
  double coaptation_weight = 5.0;
  double smoothness_weight = 0.5;
  double shape_prior_weight = 0.5;
};

struct EditOperation {
  enum class Type : std::uint8_t {
    kMoveLandmark = 0,
    kMoveCurveHandle,
    kMoveSurfaceHandle,
    kReplaceContourOnSlice,
    kLockLandmark,
  };

  Type type = Type::kMoveLandmark;
  LandmarkId landmark_id = LandmarkId::kAnteriorAnnulus;
  std::vector<Vec3d> points;
  bool hard_constraint = false;
};

struct EditSession {
  std::vector<EditOperation> operations;
  bool requires_refit = true;
};

struct MeasurementContext {
  std::optional<MitralValveModel> end_diastolic_model;
  std::optional<MitralValveModel> end_systolic_model;
  Axis3d lv_long_axis;
};

struct TrigoneExtractionResult {
  LandmarkCandidate left_trigone;
  LandmarkCandidate right_trigone;
  Polyline3d anterior_fibrous_arc;
  double continuity_score = 0.0;
};

class EvidenceBuilder {
 public:
  virtual ~EvidenceBuilder() = default;
  virtual VolumeEvidence Build(const IntensityVolume& intensity,
                               const LabelVolume& hard_labels,
                               const std::optional<std::unordered_map<LabelClass, ProbabilityVolume>>& probabilities)
      const = 0;
};

class LabelEvidenceBuilder {
 public:
  virtual ~LabelEvidenceBuilder() = default;
  virtual std::unordered_map<LabelClass, DistanceFieldVolume> BuildSignedDistanceFields(
      const LabelVolume& hard_labels) const = 0;
  virtual std::unordered_map<LabelClass, DistanceFieldVolume> BuildBoundaryShellFields(
      const LabelVolume& hard_labels) const = 0;
  virtual std::unordered_map<LabelClass, VoxelQualityMap> BuildDerivedQualityMaps(
      const LabelVolume& hard_labels) const = 0;
};

class TensorFeatureExtractor {
 public:
  virtual ~TensorFeatureExtractor() = default;
  virtual TensorDerivedData Build(const IntensityVolume& intensity,
                                  const LabelVolume& hard_labels,
                                  const std::optional<std::unordered_map<LabelClass, ProbabilityVolume>>& probabilities)
      const = 0;
};

class TrigoneExtractor {
 public:
  virtual ~TrigoneExtractor() = default;
  virtual TrigoneExtractionResult Extract(const TensorDerivedData& tensor_data,
                                          const AnnulusModel& annulus,
                                          const AorticModel& aortic,
                                          const LandmarkSet& seed_landmarks,
                                          const ReconstructionOptions& options) const = 0;
};

class LandmarkInitializer {
 public:
  virtual ~LandmarkInitializer() = default;
  virtual LandmarkSet Suggest(const VolumeEvidence& evidence,
                              CardiacPhase phase) const = 0;
};

class AnnulusReconstructor {
 public:
  virtual ~AnnulusReconstructor() = default;
  virtual AnnulusModel Reconstruct(const VolumeEvidence& evidence,
                                   const LandmarkSet& landmarks,
                                   const ReconstructionOptions& options) const = 0;
};

class AorticReconstructor {
 public:
  virtual ~AorticReconstructor() = default;
  virtual AorticModel Reconstruct(const VolumeEvidence& evidence,
                                  const LandmarkSet& landmarks,
                                  const ReconstructionOptions& options) const = 0;
};

class LeafletReconstructor {
 public:
  virtual ~LeafletReconstructor() = default;
  virtual LeafletModel Reconstruct(LabelClass leaflet_label,
                                   const VolumeEvidence& evidence,
                                   const AnnulusModel& annulus,
                                   const AorticModel& aortic,
                                   const LandmarkSet& landmarks,
                                   const ReconstructionOptions& options) const = 0;
};

class CoaptationReconstructor {
 public:
  virtual ~CoaptationReconstructor() = default;
  virtual CoaptationModel Reconstruct(const AnnulusModel& annulus,
                                      const LeafletModel& anterior,
                                      const LeafletModel& posterior,
                                      const LandmarkSet& landmarks,
                                      const ReconstructionOptions& options) const = 0;
};

class ModelRefitter {
 public:
  virtual ~ModelRefitter() = default;
  virtual MitralValveModel ApplyEdits(const MitralValveModel& input,
                                      const VolumeEvidence& evidence,
                                      const EditSession& edits,
                                      const ReconstructionOptions& options) const = 0;
};

class TemporalTracker {
 public:
  virtual ~TemporalTracker() = default;
  virtual std::vector<MitralValveModel> TrackSystole(
      const std::vector<VolumeEvidence>& frames,
      const MitralValveModel& seed_model,
      const ReconstructionOptions& options) const = 0;
};

class HeatmapGenerator {
 public:
  virtual ~HeatmapGenerator() = default;
  virtual HeatmapField ComputeSignedHeightMap(const SurfaceMesh& leaflet,
                                              const Plane3d& reference_plane) const = 0;
  virtual HeatmapField ComputeSignedSaddleHeightMap(const SurfaceMesh& leaflet,
                                                    const AnnulusModel& annulus) const = 0;
};

class MeasurementEngine {
 public:
  virtual ~MeasurementEngine() = default;

  virtual std::map<MeasurementId, ScalarMeasurement> Compute(
      const MitralValveModel& model,
      const MeasurementContext& context) const = 0;

  // Core measurement helpers for GE 4D Auto MVQ parity.
  virtual ScalarMeasurement ComputeAnnulusPerimeter3D(const AnnulusModel& annulus) const = 0;
  virtual ScalarMeasurement ComputeAnnulusArea3D(const AnnulusModel& annulus) const = 0;
  virtual ScalarMeasurement ComputeAnnulusArea2D(const AnnulusModel& annulus) const = 0;
  virtual ScalarMeasurement ComputeAPDiameter(const AnnulusModel& annulus,
                                              const LandmarkSet& landmarks) const = 0;
  virtual ScalarMeasurement ComputeALPMDiameter(const AnnulusModel& annulus,
                                                const LandmarkSet& landmarks) const = 0;
  virtual ScalarMeasurement ComputeCommissuralDiameter(const LandmarkSet& landmarks) const = 0;
  virtual ScalarMeasurement ComputeInterTrigonalDistance(const LandmarkSet& landmarks) const = 0;
  virtual ScalarMeasurement ComputeDShapeArea2D(const AnnulusModel& annulus,
                                                const LandmarkSet& landmarks) const = 0;
  virtual ScalarMeasurement ComputeDShapePerimeter(const AnnulusModel& annulus,
                                                   const LandmarkSet& landmarks) const = 0;
  virtual ScalarMeasurement ComputeAnnulusHeight(const AnnulusModel& annulus) const = 0;
  virtual ScalarMeasurement ComputeNonPlanarAngle(const AnnulusModel& annulus,
                                                  const LandmarkSet& landmarks) const = 0;
  virtual ScalarMeasurement ComputeMitralAorticAngle(const AnnulusModel& annulus,
                                                     const AorticModel& aortic) const = 0;
  virtual ScalarMeasurement ComputeMitralAnnularExcursion(const MitralValveModel& ed,
                                                          const MitralValveModel& es,
                                                          const Axis3d& lv_long_axis) const = 0;
  virtual ScalarMeasurement ComputeAnnularAreaFraction(const MitralValveModel& ed,
                                                       const MitralValveModel& es) const = 0;
  virtual ScalarMeasurement ComputeAnnularVelocity(const std::vector<MitralValveModel>& systolic_models,
                                                   const Axis3d& lv_long_axis) const = 0;
  virtual ScalarMeasurement ComputeLeafletArea(const LeafletModel& leaflet) const = 0;
  virtual ScalarMeasurement ComputeLeafletLength(const LeafletModel& leaflet) const = 0;
  virtual ScalarMeasurement ComputeLeafletAngle(const LeafletModel& leaflet,
                                                const AnnulusModel& annulus) const = 0;
  virtual ScalarMeasurement ComputeTentingHeight(const CoaptationModel& coaptation,
                                                 const AnnulusModel& annulus) const = 0;
  virtual ScalarMeasurement ComputeTentingArea(const LeafletModel& anterior,
                                               const LeafletModel& posterior,
                                               const AnnulusModel& annulus,
                                               const CoaptationModel& coaptation) const = 0;
  virtual ScalarMeasurement ComputeTentingVolume(const LeafletModel& anterior,
                                                 const LeafletModel& posterior,
                                                 const AnnulusModel& annulus,
                                                 const CoaptationModel& coaptation) const = 0;
  virtual ScalarMeasurement ComputeBillowingHeight(const LeafletModel& anterior,
                                                   const LeafletModel& posterior,
                                                   const AnnulusModel& annulus) const = 0;
  virtual ScalarMeasurement ComputeBillowingArea(const LeafletModel& anterior,
                                                 const LeafletModel& posterior,
                                                 const AnnulusModel& annulus) const = 0;
  virtual ScalarMeasurement ComputeBillowingVolume(const LeafletModel& anterior,
                                                   const LeafletModel& posterior,
                                                   const AnnulusModel& annulus) const = 0;
  virtual ScalarMeasurement ComputeCoaptationLength(const CoaptationModel& coaptation) const = 0;
  virtual ScalarMeasurement ComputeCoaptationArea(const CoaptationModel& coaptation) const = 0;
  virtual ScalarMeasurement ComputeOrificeArea(const CoaptationModel& coaptation) const = 0;
};

class ReportExporter {
 public:
  virtual ~ReportExporter() = default;
  virtual std::string ExportJson(const MitralValveModel& model) const = 0;
  virtual std::string ExportCsv(const MitralValveModel& model) const = 0;
};

class MVQWorkflowController {
 public:
  MVQWorkflowController(std::shared_ptr<EvidenceBuilder> evidence_builder,
                        std::shared_ptr<LandmarkInitializer> landmark_initializer,
                        std::shared_ptr<AnnulusReconstructor> annulus_reconstructor,
                        std::shared_ptr<AorticReconstructor> aortic_reconstructor,
                        std::shared_ptr<LeafletReconstructor> leaflet_reconstructor,
                        std::shared_ptr<CoaptationReconstructor> coaptation_reconstructor,
                        std::shared_ptr<ModelRefitter> model_refitter,
                        std::shared_ptr<MeasurementEngine> measurement_engine,
                        std::shared_ptr<HeatmapGenerator> heatmap_generator);

  MitralValveModel BuildInitialModel(
      const IntensityVolume& intensity,
      const LabelVolume& hard_labels,
      CardiacPhase phase,
      const ReconstructionOptions& options,
      const std::optional<std::unordered_map<LabelClass, ProbabilityVolume>>& probabilities = std::nullopt) const;

  MitralValveModel ApplyHumanEdits(
      const MitralValveModel& model,
      const IntensityVolume& intensity,
      const LabelVolume& hard_labels,
      const EditSession& edits,
      const ReconstructionOptions& options,
      const std::optional<std::unordered_map<LabelClass, ProbabilityVolume>>& probabilities = std::nullopt) const;

  MitralValveModel RecomputeMeasurements(
      const MitralValveModel& model,
      const MeasurementContext& context) const;

 private:
  std::shared_ptr<EvidenceBuilder> evidence_builder_;
  std::shared_ptr<LandmarkInitializer> landmark_initializer_;
  std::shared_ptr<AnnulusReconstructor> annulus_reconstructor_;
  std::shared_ptr<AorticReconstructor> aortic_reconstructor_;
  std::shared_ptr<LeafletReconstructor> leaflet_reconstructor_;
  std::shared_ptr<CoaptationReconstructor> coaptation_reconstructor_;
  std::shared_ptr<ModelRefitter> model_refitter_;
  std::shared_ptr<MeasurementEngine> measurement_engine_;
  std::shared_ptr<HeatmapGenerator> heatmap_generator_;
};

class RuleBasedTrigoneExtractor final : public TrigoneExtractor {
 public:
  TrigoneExtractionResult Extract(const TensorDerivedData& tensor_data,
                                  const AnnulusModel& annulus,
                                  const AorticModel& aortic,
                                  const LandmarkSet& seed_landmarks,
                                  const ReconstructionOptions& options) const override;
};

namespace geometry {

double ComputePolylineLength(const Polyline3d& line);
double ComputePointToPlaneSignedDistance(const Vec3d& point, const Plane3d& plane);
Vec3d ComputeCentroid(const std::vector<Vec3d>& points);
double ComputeTriangleArea(const Vec3d& a, const Vec3d& b, const Vec3d& c);
double ComputeMeshArea(const SurfaceMesh& mesh);
double ComputeDistance(const Vec3d& a, const Vec3d& b);
double ComputeAngleDegrees(const Vec3d& a, const Vec3d& b);
Vec3d ProjectPointToPlane(const Vec3d& point, const Plane3d& plane);

}  // namespace geometry

}  // namespace mvq
