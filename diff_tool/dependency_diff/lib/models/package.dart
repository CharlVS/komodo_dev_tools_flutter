import 'package:dependency_diff/models/description.dart';
import 'package:equatable/equatable.dart';
import 'package:yaml/yaml.dart';

class Package extends Equatable {
  final String dependency;
  final Description description;
  final String source;
  final String version;

  Package({
    required this.dependency,
    required this.description,
    required this.source,
    required this.version,
  });

  factory Package.fromYaml(YamlMap yaml) {
    Description description;
    if (yaml['description'] is String) {
      final String name = yaml['description'].toString();
      description = Description(name: name, sha256: name, url: name);
    } else {
      description = Description.fromYaml(yaml['description']);
    }

    return Package(
      dependency: yaml['dependency'],
      description: description,
      source: yaml['source'],
      version: yaml['version'],
    );
  }

  @override
  List<Object?> get props => [dependency, description, source, version];
}
