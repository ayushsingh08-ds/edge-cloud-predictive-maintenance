import 'dart:ui';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:provider/provider.dart';
import '../models/models.dart';
import '../providers/layout_provider.dart';
import '../providers/simulation_provider.dart';
import 'neumorphic_theme.dart';

class FactoryCanvas extends StatefulWidget {
  const FactoryCanvas({Key? key}) : super(key: key);

  @override
  _FactoryCanvasState createState() => _FactoryCanvasState();
}

class _FactoryCanvasState extends State<FactoryCanvas>
    with SingleTickerProviderStateMixin {
  final TransformationController _transformationController =
      TransformationController();
  late AnimationController _flowController;
  int _lastFocusRequestId = -1;
  int _lastFitRequestId = -1;
  final Map<String, List<double>> _jobAnimations = {}; 
// edgeId -> list of progress values [0..1]
  final Map<String, List<DateTime>> _jobStartTimes = {}; // edgeId -> list of start times

  @override
  void initState() {
    super.initState();
    _flowController = AnimationController(
      vsync: this,
      duration: const Duration(seconds: 1),
    )..repeat();

    final simulation = Provider.of<SimulationProvider>(context, listen: false);
    simulation.onRoutingDecision = (edgeId) {
      if (edgeId == null || !mounted) return;
      setState(() {
        _jobAnimations.putIfAbsent(edgeId, () => []).add(0.0);
        _jobStartTimes.putIfAbsent(edgeId, () => []).add(DateTime.now());
      });
    };

    // Start view centered on the large industrial floor
    WidgetsBinding.instance.addPostFrameCallback((_) {
      _transformationController.value = Matrix4.identity()
        ..translate(-3600.0, -3600.0)
        ..scale(0.85);
    });
  }

  @override
  void dispose() {
    _flowController.dispose();
    _transformationController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final layout = Provider.of<LayoutProvider>(context);
    final simulation = Provider.of<SimulationProvider>(context);

    if (layout.focusRequestId != _lastFocusRequestId &&
        layout.focusNodeId != null) {
      _lastFocusRequestId = layout.focusRequestId;
      WidgetsBinding.instance.addPostFrameCallback((_) {
        _centerOnNode(layout.focusNodeId!, layout);
      });
    }

    if (layout.fitRequestId != _lastFitRequestId) {
      _lastFitRequestId = layout.fitRequestId;
      WidgetsBinding.instance.addPostFrameCallback((_) {
        _fitToNodes(layout);
      });
    }

    if (simulation.isSimulating && !_flowController.isAnimating) {
      _flowController.repeat();
    } else if (!simulation.isSimulating && _flowController.isAnimating) {
      _flowController.stop();
    }

    return MouseRegion(
      cursor: _getCursorForTool(layout.currentTool),
      onHover: (event) {
        final scenePos = _transformationController.toScene(event.localPosition);
        layout.updateMousePosition(scenePos);
      },
      child: Container(
        color: NeumorphicColors.background(layout.isDarkMode),
        child: GestureDetector(
          onTapDown: (details) {
            final scenePos = _transformationController.toScene(
              details.localPosition,
            );
            if (layout.currentTool == EditorTool.deleteEdge) {
              _handleEdgeClickAt(layout, scenePos);
            } else if (layout.currentTool == EditorTool.select) {
              layout.selectNode(null);
            }
          },
          // selection box is triggered by marquee now removed, reverting to click-drag on background only in Select mode
          onPanStart: (details) => layout.startSelectionBox(
            _transformationController.toScene(details.localPosition),
          ),
          onPanUpdate: (details) => layout.updateSelectionBox(
            _transformationController.toScene(details.localPosition),
          ),
          onPanEnd: (details) => layout.endSelectionBox(),
          child: AnimatedContainer(
            duration: const Duration(milliseconds: 600),
            curve: Curves.easeInOutCubic,
            child: InteractiveViewer(
              transformationController: _transformationController,
              boundaryMargin: const EdgeInsets.all(4000),
              minScale: 0.05,
              maxScale: 3.5,
              constrained: false,
              child: Transform(
                transform: layout.isometricMode
                    ? (Matrix4.identity()
                      ..setEntry(3, 2, 0.0008)
                      ..rotateX(0.8)
                      ..rotateZ(-0.6)
                      ..translate(-100.0, 50.0))
                    : Matrix4.identity(),
                alignment: FractionalOffset.center,
                child: Stack(
              clipBehavior: Clip.none,
              children: [
                RepaintBoundary(child: const GridBackground()),
                RepaintBoundary(
                  child: AnimatedBuilder(
                    animation: _flowController,
                    builder: (context, child) {
                      return CustomPaint(
                        size: const Size(8000, 8000),
                        painter: ConnectionPainter(
                          nodes: layout.nodes,
                          edges: layout.edges,
                          flowOffset: _flowController.value,
                          speedMultiplier: simulation.speedMultiplier,
                          isSimulating: simulation.isSimulating,
                          currentTool: layout.currentTool,
                          connectSourceId: layout.connectSourceNodeId,
                          mousePosition: layout.mousePosition,
                          highlightedEdges: layout.highlightedEdges,
                          activePathId: layout.activePathId,
                          candidateEdges: layout.candidateEdges,
                          jobFlows: _updateAndGetJobFlows(simulation.speedMultiplier),
                          isDarkMode: layout.isDarkMode,
                        ),
                      );
                    },
                  ),
                ),
                  ...layout.nodes.map((node) {
                    return PositionedNode(key: ValueKey(node.id), node: node);
                  }).toList(),
                  if (layout.selectionRect != null)
                    Positioned.fromRect(
                      rect: layout.selectionRect!,
                      child: Container(
                        decoration: BoxDecoration(
                          color: NeumorphicColors.accent(
                            layout.isDarkMode,
                          ).withOpacity(0.12),
                          border: Border.all(
                            color: NeumorphicColors.accent(layout.isDarkMode),
                            width: 1.5,
                          ),
                          borderRadius: BorderRadius.circular(4),
                        ),
                      ),
                    ),
                  if (layout.heatmapMode) const HeatmapLegend(),
                ],
              ),
            ),
          ),
        ),
      ),
    ),
  );
}

  void _centerOnNode(String nodeId, LayoutProvider layout) {
    final nodeIndex = layout.nodes.indexWhere((n) => n.id == nodeId);
    if (nodeIndex < 0) {
      return;
    }

    final renderObject = context.findRenderObject();
    if (renderObject is! RenderBox || !renderObject.hasSize) {
      return;
    }

    final viewportSize = renderObject.size;
    final node = layout.nodes[nodeIndex];
    final target = node.position.toOffset() + const Offset(50, 50);

    final current = _transformationController.value;
    final currentScale = current.getMaxScaleOnAxis().clamp(0.2, 2.0);
    final targetScale = currentScale < 0.6 ? 0.75 : currentScale;

    final tx = (viewportSize.width / 2) - (target.dx * targetScale);
    final ty = (viewportSize.height / 2) - (target.dy * targetScale);

    _transformationController.value = Matrix4.identity()
      ..translate(tx, ty)
      ..scale(targetScale);
  }

  void _fitToNodes(LayoutProvider layout) {
    if (layout.nodes.isEmpty) {
      return;
    }

    final renderObject = context.findRenderObject();
    if (renderObject is! RenderBox || !renderObject.hasSize) {
      return;
    }

    final viewport = renderObject.size;
    const nodeW = 100.0;
    const nodeH = 80.0;
    const pad = 140.0;

    double minX = layout.nodes.first.position.x;
    double minY = layout.nodes.first.position.y;
    double maxX = layout.nodes.first.position.x + nodeW;
    double maxY = layout.nodes.first.position.y + nodeH;

    for (final node in layout.nodes) {
      final x1 = node.position.x;
      final y1 = node.position.y;
      final x2 = x1 + nodeW;
      final y2 = y1 + nodeH;
      if (x1 < minX) minX = x1;
      if (y1 < minY) minY = y1;
      if (x2 > maxX) maxX = x2;
      if (y2 > maxY) maxY = y2;
    }

    final contentW = (maxX - minX) + (pad * 2);
    final contentH = (maxY - minY) + (pad * 2);

    final sx = viewport.width / contentW;
    final sy = viewport.height / contentH;
    final scale = sx < sy ? sx : sy;
    final clampedScale = scale.clamp(0.12, 1.25);

    final centerX = (minX + maxX) / 2;
    final centerY = (minY + maxY) / 2;
    final tx = (viewport.width / 2) - (centerX * clampedScale);
    final ty = (viewport.height / 2) - (centerY * clampedScale);

    _transformationController.value = Matrix4.identity()
      ..translate(tx, ty)
      ..scale(clampedScale);
  }

  MouseCursor _getCursorForTool(EditorTool tool) {
    switch (tool) {
      case EditorTool.connect:
        return SystemMouseCursors.precise;
      case EditorTool.deleteEdge:
        return SystemMouseCursors.noDrop;
      default:
        return SystemMouseCursors.basic;
    }
  }

  void _handleEdgeClickAt(LayoutProvider layout, Offset scenePos) {
    for (var edge in layout.edges) {
      final fromIdx = layout.nodes.indexWhere((n) => n.id == edge.fromNode);
      final toIdx = layout.nodes.indexWhere((n) => n.id == edge.toNode);

      if (fromIdx == -1 || toIdx == -1) continue;

      final fromNode = layout.nodes[fromIdx];
      final toNode = layout.nodes[toIdx];
      final start = fromNode.position.toOffset() + const Offset(80, 40);
      final end = toNode.position.toOffset() + const Offset(0, 40);

      if (_isPointNearBezier(scenePos, start, end)) {
        layout.deleteEdge(edge.fromNode, edge.toNode);
        return;
      }
    }
  }

  bool _isPointNearBezier(Offset point, Offset start, Offset end) {
    final path = ConnectionPainter.getBezierPath(start, end);
    final metrics = path.computeMetrics();
    for (final metric in metrics) {
      for (double i = 0; i < metric.length; i += 5) {
        final pos = metric.getTangentForOffset(i)!.position;
        if ((pos - point).distance < 20) return true;
      }
    }
    return false;
  }

  Map<String, List<double>> _updateAndGetJobFlows(double speedMultiplier) {
    final now = DateTime.now();
    final Map<String, List<double>> currentFlows = {};
    
    final keys = _jobAnimations.keys.toList();
    for (final edgeId in keys) {
      final animations = _jobAnimations[edgeId]!;
      final startTimes = _jobStartTimes[edgeId]!;
      final List<double> updated = [];
      final List<DateTime> updatedStarts = [];
      
      for (int i = 0; i < animations.length; i++) {
        final elapsed = now.difference(startTimes[i]).inMilliseconds / 1000.0;
        // Assume default transport time is 2.0s if not specified, scaled by speed
        final duration = 2.0 / (speedMultiplier > 0 ? speedMultiplier : 1.0);
        final progress = (elapsed / duration).clamp(0.0, 1.0);
        
        if (progress < 1.0) {
          updated.add(progress);
          updatedStarts.add(startTimes[i]);
        }
      }
      
      if (updated.isNotEmpty) {
        _jobAnimations[edgeId] = updated;
        _jobStartTimes[edgeId] = updatedStarts;
        currentFlows[edgeId] = updated;
      } else {
        _jobAnimations.remove(edgeId);
        _jobStartTimes.remove(edgeId);
      }
    }
    return currentFlows;
  }
}

class GridBackground extends StatelessWidget {
  const GridBackground({Key? key}) : super(key: key);
  @override
  Widget build(BuildContext context) {
    final layout = Provider.of<LayoutProvider>(context);
    return CustomPaint(
      size: const Size(8000, 8000),
      painter: GridPainter(isDark: layout.isDarkMode),
    );
  }
}

class GridPainter extends CustomPainter {
  final bool isDark;
  GridPainter({required this.isDark});

  @override
  void paint(Canvas canvas, Size size) {
    final paint = Paint()
      ..color = NeumorphicColors.darkShadow(isDark).withOpacity(0.08)
      ..strokeWidth = 1.0;
    const step = 20.0;
    for (double i = 0; i <= size.width; i += step)
      canvas.drawLine(Offset(i, 0), Offset(i, size.height), paint);
    for (double i = 0; i <= size.height; i += step)
      canvas.drawLine(Offset(0, i), Offset(size.width, i), paint);
  }

  @override
  bool shouldRepaint(covariant CustomPainter oldDelegate) => false;
}

class ConnectionPainter extends CustomPainter {
  final List<LayoutNode> nodes;
  final List<LayoutEdge> edges;
  final double flowOffset;
  final double speedMultiplier;
  final bool isSimulating;
  final EditorTool currentTool;
  final String? connectSourceId;
  final Offset? mousePosition;

  final Set<String> highlightedEdges; // User selection or manual highlight
  final Set<String> candidateEdges; // Routing candidates (GHOSTED CYAN)
  final String? activePathId; // Routing decision (PULSING GREEN)
  final Map<String, List<double>> jobFlows; // edgeId -> List of progress [0..1]
  final bool isDarkMode;

  ConnectionPainter({
    required this.nodes,
    required this.edges,
    required this.flowOffset,
    required this.speedMultiplier,
    required this.isSimulating,
    required this.currentTool,
    this.connectSourceId,
    this.mousePosition,
    this.highlightedEdges = const {},
    this.candidateEdges = const {},
    this.activePathId,
    this.jobFlows = const {},
    required this.isDarkMode,
  });

  @override
  void paint(Canvas canvas, Size size) {
    final pipePaint = Paint()
      ..color = Colors.white.withOpacity(0.12)
      ..strokeWidth = 12.0
      ..style = PaintingStyle.stroke
      ..strokeCap = StrokeCap.round;

    final flowPaint = Paint()
      ..color = NeumorphicColors.accent(isDarkMode).withOpacity(0.6)
      ..strokeWidth = 3.0
      ..style = PaintingStyle.stroke
      ..strokeCap = StrokeCap.round;

    for (final edge in edges) {
      final fromIdx = nodes.indexWhere((n) => n.id == edge.fromNode);
      final toIdx = nodes.indexWhere((n) => n.id == edge.toNode);
      if (fromIdx == -1 || toIdx == -1) continue;

      final startNode = nodes[fromIdx];
      final toNode = nodes[toIdx];
      final start =
          startNode.position.toOffset() +
          (startNode.type == LayoutNodeType.machine
              ? const Offset(100, 55)
              : const Offset(90, 50));
      final end =
          toNode.position.toOffset() +
          (toNode.type == LayoutNodeType.machine
              ? const Offset(0, 55)
              : const Offset(0, 50));
      final path = getBezierPath(start, end);
      final edgeId = '${edge.fromNode}_to_${edge.toNode}';

      bool isActive = activePathId == edgeId;
      bool isCandidate =
          candidateEdges.contains(edgeId) || highlightedEdges.contains(edgeId);
      final highlightLine = currentTool == EditorTool.deleteEdge;

      // Color Palette for Routing
      final Color routingColor = isActive
          ? Colors.greenAccent
          : (candidateEdges.contains(edgeId)
                ? Colors.cyanAccent
                : NeumorphicColors.accent(isDarkMode));

      // Draw Pipe
      canvas.drawPath(
        path,
        pipePaint
          ..color = isActive
              ? routingColor.withOpacity(0.2)
              : (isCandidate
                    ? routingColor.withOpacity(0.12)
                    : (highlightLine
                          ? Colors.red.withOpacity(0.15)
                          : Colors.white.withOpacity(0.12))),
      );

      if (isCandidate || isActive) {
        final highlightPaint = Paint()
          ..color = routingColor.withOpacity(isActive ? 0.8 : 0.4)
          ..strokeWidth = isActive ? 5 : 2
          ..style = PaintingStyle.stroke
          ..strokeCap = StrokeCap.round;

        if (candidateEdges.contains(edgeId) && !isActive) {
          // Dashed line effect for candidates
          _drawDashedPath(canvas, path, highlightPaint);
        } else {
          canvas.drawPath(path, highlightPaint);
        }
      }

      // Draw Static Direction Arrow
      _drawDirectionArrow(
        canvas,
        path,
        isActive
            ? routingColor
            : (isCandidate
                  ? routingColor.withOpacity(0.6)
                  : NeumorphicColors.accent(isDarkMode).withOpacity(0.4)),
      );

      if (isSimulating || isActive) {
        final currentFlowPaint = flowPaint
          ..color = isActive
              ? Colors.greenAccent
              : routingColor.withOpacity(0.6);
        _drawAnimatedDashes(
          canvas,
          path,
          currentFlowPaint,
          isDecision: isActive,
        );
      } else {
        canvas.drawPath(
          path,
          flowPaint
            ..color = isCandidate
                ? routingColor.withOpacity(0.3)
                : NeumorphicColors.accent(isDarkMode).withOpacity(0.2),
        );
      }

      // Draw Individual Job Dots
      if (jobFlows.containsKey(edgeId)) {
        final jobDotPaint = Paint()
          ..color = Colors.cyanAccent
          ..style = PaintingStyle.fill;
          
        final glowPaint = Paint()
          ..color = Colors.cyanAccent.withOpacity(0.3)
          ..maskFilter = const MaskFilter.blur(BlurStyle.normal, 4);

        for (final progress in jobFlows[edgeId]!) {
          final metrics = path.computeMetrics();
          for (final metric in metrics) {
            final pos = metric.getTangentForOffset(metric.length * progress)?.position;
            if (pos != null) {
              canvas.drawCircle(pos, 5, glowPaint);
              canvas.drawCircle(pos, 3, jobDotPaint);
            }
          }
        }
      }
    }

    if (currentTool == EditorTool.connect &&
        connectSourceId != null &&
        nodes.isNotEmpty) {
      final sourceIdx = nodes.indexWhere((n) => n.id == connectSourceId);
      if (sourceIdx != -1 && mousePosition != null) {
        final sourceNode = nodes[sourceIdx];
        final start = sourceNode.position.toOffset() + const Offset(80, 40);
        final path = getBezierPath(start, mousePosition!);
        canvas.drawPath(
          path,
          Paint()
            ..color = Colors.green.withOpacity(0.1)
            ..strokeWidth = 8
            ..style = PaintingStyle.stroke
            ..strokeCap = StrokeCap.round,
        );
        canvas.drawPath(
          path,
          Paint()
            ..color = Colors.green.withOpacity(0.4)
            ..strokeWidth = 2
            ..style = PaintingStyle.stroke
            ..strokeCap = StrokeCap.round
            ..maskFilter = const MaskFilter.blur(BlurStyle.normal, 2),
        );
      }
    }
  }

  static Path getBezierPath(Offset start, Offset end) {
    final path = Path();
    path.moveTo(start.dx, start.dy);
    final dx = (end.dx - start.dx).abs() / 2;
    path.cubicTo(
      start.dx + dx.clamp(40, 150),
      start.dy,
      end.dx - dx.clamp(40, 150),
      end.dy,
      end.dx,
      end.dy,
    );
    return path;
  }

  void _drawDirectionArrow(Canvas canvas, Path path, Color color) {
    final metrics = path.computeMetrics();

    for (final metric in metrics) {
      final midpoint = metric.length * 0.5;
      final tangent = metric.getTangentForOffset(midpoint);
      if (tangent == null) continue;

      final pos = tangent.position;
      final angle = -tangent.angle;

      final arrowPath = Path()
        ..moveTo(0, -6)
        ..lineTo(10, 0)
        ..lineTo(0, 6)
        ..close();

      canvas.save();
      canvas.translate(pos.dx, pos.dy);
      canvas.rotate(-angle);
      canvas.drawPath(arrowPath, Paint()..color = color);
      canvas.restore();

      // We only need to draw one arrow in the middle of the first segment
      break;
    }
  }

  void _drawAnimatedDashes(
    Canvas canvas,
    Path path,
    Paint paint, {
    bool isDecision = false,
  }) {
    final pathMetrics = path.computeMetrics();
    final dashWidth = isDecision ? 12.0 : 8.0;
    final dashSpace = isDecision ? 12.0 : 20.0;
    for (final metric in pathMetrics) {
      final totalLength = metric.length;
      final offset =
          (flowOffset * (isDecision ? 2.0 : speedMultiplier) % 1.0) *
          (dashWidth + dashSpace);
      double currentPos = offset;
      while (currentPos < totalLength) {
        final startPos = currentPos;
        final endPos = (currentPos + dashWidth).clamp(0.0, totalLength);
        canvas.drawPath(metric.extractPath(startPos, endPos), paint);
        currentPos += dashWidth + dashSpace;
      }
    }
  }

  void _drawDashedPath(Canvas canvas, Path path, Paint paint) {
    const double dashWidth = 10.0;
    const double dashSpace = 8.0;
    final metrics = path.computeMetrics();
    for (final metric in metrics) {
      double distance = 0.0;
      while (distance < metric.length) {
        final start = distance;
        final end = (distance + dashWidth).clamp(0.0, metric.length);
        canvas.drawPath(metric.extractPath(start, end), paint);
        distance += dashWidth + dashSpace;
      }
    }
  }

  @override
  bool shouldRepaint(covariant ConnectionPainter oldDelegate) => true;
}

class PositionedNode extends StatefulWidget {
  final LayoutNode node;
  const PositionedNode({required Key key, required this.node})
    : super(key: key);
  @override
  _PositionedNodeState createState() => _PositionedNodeState();
}

class _PositionedNodeState extends State<PositionedNode>
    with SingleTickerProviderStateMixin {
  bool _isHovered = false;
  late AnimationController _glowController;

  @override
  void initState() {
    super.initState();
    _glowController = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 1500),
    )..repeat(reverse: true);
  }

  @override
  void dispose() {
    _glowController.dispose();
    super.dispose();
  }

  Color _getHeatmapColor(double utilization) {
    if (utilization < 50) return Colors.transparent;
    if (utilization < 70) return Colors.brown.withOpacity(0.15); // Light Brown
    if (utilization < 85) return Colors.orange.withOpacity(0.35); // Orange
    return Colors.red.withOpacity(0.5); // Red Glow
  }

  @override
  Widget build(BuildContext context) {
    final layout = Provider.of<LayoutProvider>(context);
    final simulation = Provider.of<SimulationProvider>(context);
    final isSelected = layout.selectedNodeIds.contains(widget.node.id);
    final isConnectSource = layout.connectSourceNodeId == widget.node.id;
    final metrics =
        simulation.machineMetrics[widget.node.id] ??
        simulation.machineMetrics[widget.node.id.toLowerCase()];

    return Positioned(
      left: widget.node.position.x,
      top: widget.node.position.y,
      child: Stack(
        clipBehavior: Clip.none,
        children: [
          // ID Label (Floating on top)
          Positioned(
            top: -22,
            left: -20,
            right: -20,
            child: Text(
              widget.node.id.toUpperCase(),
              textAlign: TextAlign.center,
              style: TextStyle(
                fontSize: 9,
                fontWeight: FontWeight.w900,
                color: NeumorphicColors.text(
                  layout.isDarkMode,
                ).withOpacity(0.5),
                letterSpacing: 1.2,
              ),
            ),
          ),
          MouseRegion(
            onEnter: (_) => setState(() => _isHovered = true),
            onExit: (_) => setState(() => _isHovered = false),
            child: GestureDetector(
              onPanUpdate: (details) =>
                  layout.updateNodePosition(widget.node.id, details.delta),
              onPanEnd: (_) => layout.updateNodePosition(
                widget.node.id,
                Offset.zero,
                isFinal: true,
              ),
              onTap: () => layout.handleNodeClick(widget.node.id),
              child: AnimatedScale(
                scale: _isHovered ? 1.02 : 1.0,
                duration: const Duration(milliseconds: 200),
                child: Container(
                  width: width,
                  height: height,
                  decoration:
                      NeumorphicTheme.decoration(
                        isDark: layout.isDarkMode,
                        borderRadius: BorderRadius.circular(16),
                        color:
                            layout.heatmapMode &&
                                widget.node.type == LayoutNodeType.machine &&
                                metrics != null
                            ? _getHeatmapColor(metrics.utilization)
                            : (isSelected
                                  ? NeumorphicColors.accent(
                                      layout.isDarkMode,
                                    ).withOpacity(0.08)
                                  : null),
                      ).copyWith(
                        border: Border.all(
                          color: isConnectSource
                              ? Colors.green
                              : (isSelected
                                    ? NeumorphicColors.accent(layout.isDarkMode)
                                    : Colors.transparent),
                          width: isConnectSource
                              ? 2.5
                              : (isSelected ? 2.0 : 0.0),
                        ),
                        boxShadow: _getGlowShadows(
                          widget.node,
                          metrics,
                          _glowController.value,
                        ),
                      ),
                  child: ExcludeSemantics(
                    child: _buildNodeContent(
                      widget.node,
                      metrics,
                      isConnectSource,
                      layout.isDarkMode,
                    ),
                  ),
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }

  double get width => widget.node.type == LayoutNodeType.machine ? 100 : 90;
  double get height => widget.node.type == LayoutNodeType.machine ? 132 : 115;

  List<BoxShadow>? _getGlowShadows(
    LayoutNode node,
    MachineMetrics? metrics,
    double pulse,
  ) {
    if (node.type == LayoutNodeType.machine && metrics != null) {
      if (metrics.healthIndex < 30) {
        return [
          BoxShadow(
            color: Colors.red.withOpacity(0.4 * pulse),
            blurRadius: 15 * pulse,
            spreadRadius: 2,
          ),
        ];
      }
      if (metrics.congestionRisk > 0.6) {
        return [
          BoxShadow(
            color: Colors.orange.withOpacity(0.4 * pulse),
            blurRadius: 15 * pulse,
            spreadRadius: 2,
          ),
        ];
      }
    }
    return null;
  }

  Widget _buildNodeContent(
    LayoutNode node,
    MachineMetrics? metrics,
    bool isConnectSource,
    bool isDark,
  ) {
    if (node.type == LayoutNodeType.machine) {
      return _buildMachineCard(node, metrics, isConnectSource, isDark);
    } else if (node.type == LayoutNodeType.buffer) {
      return _buildBufferCard(node, isConnectSource, isDark);
    }

    return Column(
      mainAxisAlignment: MainAxisAlignment.center,
      children: [
        Icon(
          _getIconForType(node.type),
          color: isConnectSource
              ? Colors.green
              : NeumorphicColors.accent(isDark),
          size: 28,
        ),
        const SizedBox(height: 4),
        Text(
          node.id,
          style: TextStyle(
            fontSize: 9,
            fontWeight: FontWeight.bold,
            color: NeumorphicColors.text(isDark),
          ),
        ),
      ],
    );
  }

  Widget _buildMachineCard(
    LayoutNode node,
    MachineMetrics? metrics,
    bool isConnectSource,
    bool isDark,
  ) {
    final health = metrics?.healthIndex ?? 100.0;
    final rul = (metrics?.healthIndex ?? 100.0) * 0.8; // Mocked or calculated

    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 8.0, vertical: 4.0),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Icon(
                _getIconForType(node.type),
                size: 14,
                color: NeumorphicColors.accent(isDark).withOpacity(0.6),
              ),
              if (metrics?.status == MachineStatus.failed)
                _buildBadge('FAIL', isDark, color: Colors.red, pulse: true)
              else if (metrics?.status == MachineStatus.maintenance)
                _buildBadge('MAINT', isDark, color: Colors.blue),
            ],
          ),
          const Spacer(),
          Text(
            node.id,
            style: TextStyle(
              fontSize: 10,
              fontWeight: FontWeight.w900,
              letterSpacing: 0.5,
              color: NeumorphicColors.text(isDark),
            ),
          ),
          const SizedBox(height: 8),
          _buildMetricRow(
            'HEALTH',
            '${health.toStringAsFixed(0)}%',
            _getHealthColor(health),
            isDark,
          ),
          const SizedBox(height: 4),
          _buildMetricRow(
            'RUL',
            '${rul.toStringAsFixed(1)}%',
            Colors.blueAccent,
            isDark,
          ),
        ],
      ),
    );
  }

  Widget _buildBufferCard(LayoutNode node, bool isConnectSource, bool isDark) {
    final capacity = node.properties['capacity'] ?? 40;
    final count = node.queueSize;
    final percent = (count / capacity).clamp(0.0, 1.0);

    return Padding(
      padding: const EdgeInsets.all(8.0),
      child: Column(
        children: [
          Text(
            node.id,
            style: TextStyle(
              fontSize: 8,
              color: NeumorphicColors.text(isDark).withOpacity(0.5),
              fontWeight: FontWeight.bold,
            ),
          ),
          const Spacer(),
          Stack(
            alignment: Alignment.center,
            children: [
              SizedBox(
                width: 45,
                height: 45,
                child: CircularProgressIndicator(
                  value: percent,
                  strokeWidth: 6,
                  backgroundColor: NeumorphicColors.darkShadow(
                    isDark,
                  ).withOpacity(0.2),
                  valueColor: AlwaysStoppedAnimation<Color>(
                    percent > 0.8 ? Colors.redAccent : Colors.orangeAccent,
                  ),
                ),
              ),
              Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Text(
                    '$count/$capacity',
                    style: TextStyle(
                      fontSize: 10,
                      fontWeight: FontWeight.bold,
                      color: NeumorphicColors.text(isDark),
                    ),
                  ),
                  Text(
                    '${(percent * 100).toStringAsFixed(0)}%',
                    style: TextStyle(
                      fontSize: 8,
                      color: NeumorphicColors.text(isDark).withOpacity(0.6),
                    ),
                  ),
                ],
              ),
            ],
          ),
          const Spacer(),
          const Text(
            'REAL TIME',
            style: TextStyle(
              fontSize: 7,
              fontWeight: FontWeight.bold,
              letterSpacing: 1.0,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildMetricRow(String label, String value, Color color, bool isDark) {
    return Row(
      mainAxisAlignment: MainAxisAlignment.spaceBetween,
      children: [
        Text(
          label,
          style: TextStyle(
            fontSize: 7,
            fontWeight: FontWeight.bold,
            color: NeumorphicColors.text(isDark),
          ),
        ),
        Text(
          value,
          style: TextStyle(
            fontSize: 9,
            fontWeight: FontWeight.w900,
            color: color,
          ),
        ),
      ],
    );
  }

  Widget _buildBadge(
    String text,
    bool isDark, {
    Color? color,
    bool pulse = false,
  }) {
    Widget badge = Container(
      padding: const EdgeInsets.symmetric(horizontal: 4, vertical: 2),
      decoration: BoxDecoration(
        color: color ?? NeumorphicColors.accent(isDark),
        borderRadius: BorderRadius.circular(4),
      ),
      child: Text(
        text,
        style: const TextStyle(
          fontSize: 8,
          color: Colors.white,
          fontWeight: FontWeight.bold,
        ),
      ),
    );

    if (pulse) {
      return AnimatedBuilder(
        animation: _glowController,
        builder: (context, child) => Transform.scale(
          scale: 1.0 + (0.15 * _glowController.value),
          child: Opacity(
            opacity: 0.8 + (0.2 * _glowController.value),
            child: badge,
          ),
        ),
      );
    }
    return badge;
  }

  IconData _getIconForType(LayoutNodeType type) {
    switch (type) {
      case LayoutNodeType.machine:
        return Icons.settings_suggest;
      case LayoutNodeType.buffer:
        return Icons.inventory_2;
      case LayoutNodeType.source:
        return Icons.login;
      case LayoutNodeType.sink:
        return Icons.logout;
      case LayoutNodeType.divider:
        return Icons.alt_route;
      case LayoutNodeType.conveyor:
        return Icons.sync_alt;
    }
  }

  Color _getHealthColor(double value) {
    if (value > 80) return Colors.green;
    if (value > 40) return Colors.orange;
    return Colors.red;
  }
}

class HeatmapLegend extends StatelessWidget {
  const HeatmapLegend({Key? key}) : super(key: key);

  @override
  Widget build(BuildContext context) {
    final layout = Provider.of<LayoutProvider>(context);
    return Positioned(
      bottom: 24,
      left: 24,
      child: Container(
        padding: const EdgeInsets.all(12),
        decoration: NeumorphicTheme.decoration(
          isDark: layout.isDarkMode,
          borderRadius: BorderRadius.circular(12),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              'UTILIZATION HEATMAP',
              style: TextStyle(
                fontSize: 8,
                fontWeight: FontWeight.bold,
                letterSpacing: 0.8,
                color: NeumorphicColors.text(layout.isDarkMode),
              ),
            ),
            const SizedBox(height: 8),
            _buildLegendItem(
              'Critical (85%+) ',
              Colors.red.withOpacity(0.5),
              layout.isDarkMode,
            ),
            _buildLegendItem(
              'Warning (70%+) ',
              Colors.orange.withOpacity(0.4),
              layout.isDarkMode,
            ),
            _buildLegendItem(
              'Optimal (50%+) ',
              NeumorphicColors.accent(layout.isDarkMode).withOpacity(0.2),
              layout.isDarkMode,
            ),
            _buildLegendItem(
              'Low/Idle ',
              Colors.transparent,
              layout.isDarkMode,
              border: true,
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildLegendItem(
    String label,
    Color color,
    bool isDark, {
    bool border = false,
  }) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 2.0),
      child: Row(
        children: [
          Container(
            width: 12,
            height: 12,
            decoration: BoxDecoration(
              color: color,
              borderRadius: BorderRadius.circular(3),
              border: border
                  ? Border.all(
                      color: NeumorphicColors.text(isDark).withOpacity(0.2),
                    )
                  : null,
            ),
          ),
          const SizedBox(width: 8),
          Text(
            label,
            style: TextStyle(
              fontSize: 10,
              color: NeumorphicColors.text(isDark),
            ),
          ),
        ],
      ),
    );
  }
}
