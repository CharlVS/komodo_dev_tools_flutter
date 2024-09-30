import 'package:equatable/equatable.dart';
import 'package:yaml/yaml.dart';

class Description extends Equatable {
  final String name;
  final String sha256;
  final String url;

  Description({required this.name, required this.sha256, required this.url});

  factory Description.fromYaml(YamlMap yaml) {
    return Description(
      name: yaml['name'] ?? '',
      sha256: yaml['sha256'] ?? '',
      url: yaml['url'] ?? '',
    );
  }

  @override
  List<Object?> get props => [name, sha256, url];
}
