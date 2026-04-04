import 'dart:math';
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

class _FactoryCanvasState extends State<FactoryCanvas> with SingleTickerProviderStateMixin {
  final TransformationController _transformationController = TransformationController();
  late AnimationController _flowController;

  @override
  void initState() {
    super.initState();
    _flowController = AnimationController(
      vsync: this,
      duration: const Duration(seconds: 1),
    )..repeat();
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
        color: NeumorphicColors.background,
        child: GestureDetector(
          onTapDown: (details) {
            final scenePos = _transformationController.toScene(details.localPosition);
            if (layout.currentTool == EditorTool.deleteEdge) {
               _handleEdgeClickAt(layout, scenePos);
            } else if (layout.currentTool == EditorTool.select) {
               layout.selectNode(null);
            }
          },
          // selection box is triggered by marquee now removed, reverting to click-drag on background only in Select mode
          onPanStart: (details) => layout.startSelectionBox(_transformationController.toScene(details.localPosition)),
          onPanUpdate: (details) => layout.updateSelectionBox(_transformationController.toScene(details.localPosition)),
          onPanEnd: (details) => layout.endSelectionBox(),
          child: InteractiveViewer(
            transformationController: _transformationController,
            boundaryMargin: const EdgeInsets.all(1500),
            minScale: 0.1,
            maxScale: 2.5,
            child: Stack(
              clipBehavior: Clip.none,
              children: [
                const GridBackground(),
                AnimatedBuilder(
                  animation: _flowController,
                  builder: (context, child) {
                    return CustomPaint(
                      size: const Size(4000, 4000),
                      painter: ConnectionPainter(
                        nodes: layout.nodes,
                        edges: layout.edges,
                        flowOffset: _flowController.value,
                        speedMultiplier: simulation.speedMultiplier,
                        isSimulating: simulation.isSimulating,
                        currentTool: layout.currentTool,
                        connectSourceId: layout.connectSourceNodeId,
                        mousePosition: layout.mousePosition,
                      ),
                    );
                  },
                ),
                ...layout.nodes.map((node) {
                  return PositionedNode(key: ValueKey(node.id), node: node);
                }).toList(),
                if (layout.selectionRect != null)
                  Positioned.fromRect(
                    rect: layout.selectionRect!,
                    child: Container(
                      decoration: BoxDecoration(
                        color: NeumorphicColors.accent.withOpacity(0.12),
                        border: Border.all(color: NeumorphicColors.accent, width: 1.5),
                        borderRadius: BorderRadius.circular(4),
                      ),
                    ),
                  ),
              ],
            ),
          ),
        ),
      ),
    );
  }

  MouseCursor _getCursorForTool(EditorTool tool) {
    switch (tool) {
      case EditorTool.connect: return SystemMouseCursors.precise;
      case EditorTool.deleteEdge: return SystemMouseCursors.noDrop;
      default: return SystemMouseCursors.basic;
    }
  }

  void _handleEdgeClickAt(LayoutProvider layout, Offset scenePos) {
    for (var edge in layout.edges) {
      final fromNode = layout.nodes.firstWhere((n) => n.id == edge.fromNode, orElse: () => layout.nodes.first);
      final toNode = layout.nodes.firstWhere((n) => n.id == edge.toNode, orElse: () => layout.nodes.first);
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
}

class GridBackground extends StatelessWidget {
  const GridBackground({Key? key}) : super(key: key);
  @override
  Widget build(BuildContext context) {
    return CustomPaint(size: const Size(4000, 4000), painter: GridPainter());
  }
}

class GridPainter extends CustomPainter {
  @override
  void paint(Canvas canvas, Size size) {
    final paint = Paint()
      ..color = NeumorphicColors.darkShadow.withOpacity(0.08)
      ..strokeWidth = 1.0;
    const step = 20.0;
    for (double i = 0; i <= size.width; i += step) canvas.drawLine(Offset(i, 0), Offset(i, size.height), paint);
    for (double i = 0; i <= size.height; i += step) canvas.drawLine(Offset(0, i), Offset(size.width, i), paint);
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

  ConnectionPainter({
    required this.nodes,
    required this.edges,
    required this.flowOffset,
    required this.speedMultiplier,
    required this.isSimulating,
    required this.currentTool,
    this.connectSourceId,
    this.mousePosition,
  });

  @override
  void paint(Canvas canvas, Size size) {
    final pipePaint = Paint()
      ..color = Colors.white.withOpacity(0.12)
      ..strokeWidth = 12.0
      ..style = PaintingStyle.stroke
      ..strokeCap = StrokeCap.round;

    final flowPaint = Paint()
      ..color = NeumorphicColors.accent.withOpacity(0.6)
      ..strokeWidth = 3.0
      ..style = PaintingStyle.stroke
      ..strokeCap = StrokeCap.round;

    for (final edge in edges) {
      final fromIdx = nodes.indexWhere((n) => n.id == edge.fromNode);
      final toIdx = nodes.indexWhere((n) => n.id == edge.toNode);
      if (fromIdx == -1 || toIdx == -1) continue;

      final start = nodes[fromIdx].position.toOffset() + const Offset(80, 40);
      final end = nodes[toIdx].position.toOffset() + const Offset(0, 40);
      final path = getBezierPath(start, end);

      final highlightLine = currentTool == EditorTool.deleteEdge;
      canvas.drawPath(path, pipePaint..color = highlightLine ? Colors.red.withOpacity(0.15) : Colors.white.withOpacity(0.12));

      if (isSimulating) {
        _drawAnimatedDashes(canvas, path, flowPaint);
      } else {
        canvas.drawPath(path, flowPaint..color = NeumorphicColors.accent.withOpacity(0.2));
      }
    }

    if (currentTool == EditorTool.connect && connectSourceId != null && mousePosition != null) {
      final sourceNode = nodes.firstWhere((n) => n.id == connectSourceId, orElse: () => nodes.first);
      final start = sourceNode.position.toOffset() + const Offset(80, 40);
      final path = getBezierPath(start, mousePosition!);
      canvas.drawPath(path, Paint()..color = Colors.green.withOpacity(0.1)..strokeWidth = 8..style = PaintingStyle.stroke..strokeCap = StrokeCap.round);
      canvas.drawPath(path, Paint()..color = Colors.green.withOpacity(0.4)..strokeWidth = 2..style = PaintingStyle.stroke..strokeCap = StrokeCap.round..maskFilter = const MaskFilter.blur(BlurStyle.normal, 2));
    }
  }

  static Path getBezierPath(Offset start, Offset end) {
    final path = Path();
    path.moveTo(start.dx, start.dy);
    final dx = (end.dx - start.dx).abs() / 2;
    path.cubicTo(start.dx + dx.clamp(40, 150), start.dy, end.dx - dx.clamp(40, 150), end.dy, end.dx, end.dy);
    return path;
  }

  void _drawAnimatedDashes(Canvas canvas, Path path, Paint paint) {
    final pathMetrics = path.computeMetrics();
    const dashWidth = 8.0;
    const dashSpace = 20.0;
    for (final metric in pathMetrics) {
      final totalLength = metric.length;
      final offset = (flowOffset * speedMultiplier % 1.0) * (dashWidth + dashSpace);
      double currentPos = offset;
      while (currentPos < totalLength) {
        final startPos = currentPos;
        final endPos = (currentPos + dashWidth).clamp(0.0, totalLength);
        canvas.drawPath(metric.extractPath(startPos, endPos), paint);
        currentPos += dashWidth + dashSpace;
      }
    }
  }

  @override
  bool shouldRepaint(covariant ConnectionPainter oldDelegate) => true;
}

class PositionedNode extends StatefulWidget {
  final LayoutNode node;
  const PositionedNode({required Key key, required this.node}) : super(key: key);
  @override
  _PositionedNodeState createState() => _PositionedNodeState();
}

class _PositionedNodeState extends State<PositionedNode> {
  bool _isHovered = false;

  @override
  Widget build(BuildContext context) {
    final layout = Provider.of<LayoutProvider>(context);
    final simulation = Provider.of<SimulationProvider>(context);
    final isSelected = layout.selectedNodeIds.contains(widget.node.id);
    final isConnectSource = layout.connectSourceNodeId == widget.node.id;
    final metrics = simulation.machineMetrics[widget.node.id];

    return Positioned(
      left: widget.node.position.x,
      top: widget.node.position.y,
      child: MouseRegion(
        onEnter: (_) => setState(() => _isHovered = true),
        onExit: (_) => setState(() => _isHovered = false),
        child: GestureDetector(
          onPanUpdate: (details) => layout.updateNodePosition(widget.node.id, details.delta),
          onPanEnd: (_) => layout.updateNodePosition(widget.node.id, Offset.zero, isFinal: true),
          onTap: () => layout.handleNodeClick(widget.node.id),
          child: AnimatedScale(
            scale: _isHovered ? 1.05 : 1.0,
            duration: const Duration(milliseconds: 200),
            child: Container(
              width: 80,
              height: 80,
              decoration: NeumorphicTheme.decoration(
                borderRadius: BorderRadius.circular(16),
                color: isSelected ? NeumorphicColors.accent.withOpacity(0.12) : null,
              ).copyWith(
                  border: Border.all(
                color: isConnectSource ? Colors.green : (isSelected ? NeumorphicColors.accent : Colors.transparent),
                width: isConnectSource ? 3.0 : (isSelected ? 2.0 : 0.0),
              )),
              child: Stack(
                alignment: Alignment.center,
                children: [
                   if (isConnectSource)
                     Positioned(top: 4, left: 4, child: Icon(Icons.link, size: 12, color: Colors.green.withOpacity(0.8))),
                  Column(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      Icon(_getIconForType(widget.node.type), color: isConnectSource ? Colors.green : NeumorphicColors.accent, size: 28),
                      const SizedBox(height: 4),
                      Text(widget.node.type.value, style: const TextStyle(fontSize: 10, fontWeight: FontWeight.bold, color: NeumorphicColors.text)),
                    ],
                  ),
                  if (widget.node.type == LayoutNodeType.machine && metrics != null)
                     Positioned(bottom: 6, left: 12, right: 12, child: _buildProgressBar(metrics.healthIndex / 100, _getHealthColor(metrics.healthIndex))),
                  if (widget.node.type == LayoutNodeType.buffer)
                     Positioned(top: 6, right: 6, child: _buildBadge(widget.node.queueSize.toString())),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildProgressBar(double value, Color color) {
    return Container(
      height: 4,
      decoration: BoxDecoration(color: Colors.black12, borderRadius: BorderRadius.circular(2)),
      child: FractionallySizedBox(alignment: Alignment.centerLeft, widthFactor: value.clamp(0.0, 1.0), child: Container(decoration: BoxDecoration(color: color, borderRadius: BorderRadius.circular(2)))),
    );
  }

  Widget _buildBadge(String text) {
    return Container(padding: const EdgeInsets.symmetric(horizontal: 4, vertical: 2), decoration: BoxDecoration(color: NeumorphicColors.accent, borderRadius: BorderRadius.circular(4)), child: Text(text, style: const TextStyle(fontSize: 8, color: Colors.white, fontWeight: FontWeight.bold)));
  }

  IconData _getIconForType(LayoutNodeType type) {
    switch (type) {
      case LayoutNodeType.machine: return Icons.settings_suggest;
      case LayoutNodeType.buffer: return Icons.inventory_2;
      case LayoutNodeType.source: return Icons.login;
      case LayoutNodeType.sink: return Icons.logout;
      case LayoutNodeType.divider: return Icons.alt_route;
      case LayoutNodeType.conveyor: return Icons.sync_alt;
    }
  }

  Color _getHealthColor(double value) {
    if (value > 80) return Colors.green;
    if (value > 40) return Colors.orange;
    return Colors.red;
  }
}
