import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../providers/layout_provider.dart';

class NeumorphicColors {
  static Color background(bool isDark) => isDark ? const Color(0xFF292D32) : const Color(0xFFE8E4D9);
  static Color lightShadow(bool isDark) => isDark ? const Color(0xFF32373D) : const Color(0xFFFFFFFF);
  static Color darkShadow(bool isDark) => isDark ? const Color(0xFF1A1D20) : const Color(0xFFD1CDC0);
  static Color accent(bool isDark) => isDark ? const Color(0xFFB3A58E) : const Color(0xFF8E806A);
  static Color text(bool isDark) => isDark ? const Color(0xFFE8E4D9).withOpacity(0.9) : const Color(0xFF5D574E);

  static Color machineIdle(bool isDark) => isDark ? const Color(0xFF90A17D) : const Color(0xFFB5C99A);
  static Color machineBusy(bool isDark) => isDark ? const Color(0xFF6B8A9E) : const Color(0xFF86A3B8);
  static Color machineFailed(bool isDark) => const Color(0xFFFF6B6B);
  static Color machineMaintenance(bool isDark) => isDark ? const Color(0xFF7A8A96) : const Color(0xFF9BABB8);
}

class NeumorphicTheme {
  static List<BoxShadow> elevatedShadows({bool isDark = false, double blurRadius = 10, Offset offset = const Offset(6, 6)}) {
    return [
      BoxShadow(
        color: NeumorphicColors.lightShadow(isDark),
        offset: -offset,
        blurRadius: blurRadius,
      ),
      BoxShadow(
        color: NeumorphicColors.darkShadow(isDark),
        offset: offset,
        blurRadius: blurRadius,
      ),
    ];
  }

  static List<BoxShadow> insetShadows({bool isDark = false, double blurRadius = 10, Offset offset = const Offset(6, 6)}) {
    return [
      BoxShadow(
        color: NeumorphicColors.darkShadow(isDark),
        offset: -offset,
        blurRadius: blurRadius,
      ),
      BoxShadow(
        color: NeumorphicColors.lightShadow(isDark),
        offset: offset,
        blurRadius: blurRadius,
      ),
    ];
  }

  static BoxDecoration decoration({
    bool isDark = false,
    BorderRadius? borderRadius,
    Color? color,
    bool isPressed = false,
  }) {
    return BoxDecoration(
      color: color ?? NeumorphicColors.background(isDark),
      borderRadius: borderRadius ?? BorderRadius.circular(16),
      boxShadow: isPressed ? insetShadows(isDark: isDark) : elevatedShadows(isDark: isDark),
    );
  }

  static BoxDecoration glassDecoration({
    bool isDark = false,
    BorderRadius? borderRadius,
    double opacity = 0.6,
  }) {
    return BoxDecoration(
      color: NeumorphicColors.background(isDark).withOpacity(opacity),
      borderRadius: borderRadius ?? BorderRadius.circular(16),
      border: Border.all(color: Colors.white.withOpacity(isDark ? 0.05 : 0.2)),
      boxShadow: elevatedShadows(isDark: isDark, blurRadius: 8, offset: const Offset(3, 3)),
    );
  }
}

class NeumorphicCard extends StatelessWidget {
  final Widget child;
  final EdgeInsetsGeometry padding;
  final double borderRadius;

  const NeumorphicCard({
    Key? key,
    required this.child,
    this.padding = const EdgeInsets.all(16.0),
    this.borderRadius = 16.0,
  }) : super(key: key);

  @override
  Widget build(BuildContext context) {
    final isDark = Provider.of<LayoutProvider>(context).isDarkMode;
    return Container(
      padding: padding,
      decoration: NeumorphicTheme.decoration(isDark: isDark, borderRadius: BorderRadius.circular(borderRadius)),
      child: child,
    );
  }
}

class NeumorphicButton extends StatefulWidget {
  final Widget child;
  final VoidCallback onPressed;
  final double borderRadius;
  final double padding;

  const NeumorphicButton({
    Key? key,
    required this.child,
    required this.onPressed,
    this.borderRadius = 12.0,
    this.padding = 12.0,
  }) : super(key: key);

  @override
  _NeumorphicButtonState createState() => _NeumorphicButtonState();
}

class _NeumorphicButtonState extends State<NeumorphicButton> with SingleTickerProviderStateMixin {
  bool _isPressed = false;

  @override
  Widget build(BuildContext context) {
    final isDark = Provider.of<LayoutProvider>(context).isDarkMode;
    return GestureDetector(
      onTapDown: (_) => setState(() => _isPressed = true),
      onTapUp: (_) {
        setState(() => _isPressed = false);
        widget.onPressed();
      },
      onTapCancel: () => setState(() => _isPressed = false),
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 100),
        padding: EdgeInsets.all(widget.padding),
        decoration: NeumorphicTheme.decoration(
          isDark: isDark,
          borderRadius: BorderRadius.circular(widget.borderRadius),
          isPressed: _isPressed,
        ),
        child: widget.child,
      ),
    );
  }
}
