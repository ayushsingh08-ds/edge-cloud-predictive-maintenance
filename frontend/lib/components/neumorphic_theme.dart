import 'package:flutter/material.dart';

class NeumorphicColors {
  static const Color background = Color(0xFFDEDBD2); // Soft Industrial Beige
  static const Color lightShadow = Color(0xFFFFFFFF);
  static const Color darkShadow = Color(0xFFB4B0A7);
  static const Color accent = Color(0xFF8E806A); // Soft Brown
  static const Color text = Color(0xFF4A4A4A);
  static const Color machineIdle = Color(0xFFB5C99A); // Soft Green
  static const Color machineBusy = Color(0xFF86A3B8); // Soft Blue
  static const Color machineFailed = Color(0xFFE89F71); // Soft Orange/Red
  static const Color machineMaintenance = Color(0xFF9BABB8); // Soft Grey
}

class NeumorphicTheme {
  static List<BoxShadow> elevatedShadows({double blurRadius = 10, Offset offset = const Offset(6, 6)}) {
    return [
      BoxShadow(
        color: NeumorphicColors.lightShadow,
        offset: -offset,
        blurRadius: blurRadius,
      ),
      BoxShadow(
        color: NeumorphicColors.darkShadow,
        offset: offset,
        blurRadius: blurRadius,
      ),
    ];
  }

  static List<BoxShadow> insetShadows({double blurRadius = 10, Offset offset = const Offset(6, 6)}) {
    // Inset is simulated in Flutter using a custom painter or by swapping colors
    // For simplicity, we'll use darker colors for the top-left and lighter for the bottom-right
    return [
      BoxShadow(
        color: NeumorphicColors.darkShadow,
        offset: -offset,
        blurRadius: blurRadius,
      ),
      BoxShadow(
        color: NeumorphicColors.lightShadow,
        offset: offset,
        blurRadius: blurRadius,
      ),
    ];
  }

  static BoxDecoration decoration({
    BorderRadius? borderRadius,
    Color? color,
    bool isPressed = false,
  }) {
    return BoxDecoration(
      color: color ?? NeumorphicColors.background,
      borderRadius: borderRadius ?? BorderRadius.circular(16),
      boxShadow: isPressed ? insetShadows() : elevatedShadows(),
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
    return Container(
      padding: padding,
      decoration: NeumorphicTheme.decoration(borderRadius: BorderRadius.circular(borderRadius)),
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
          borderRadius: BorderRadius.circular(widget.borderRadius),
          isPressed: _isPressed,
        ),
        child: widget.child,
      ),
    );
  }
}
